#!/usr/bin/env python3
"""Run genuine PE in isolated QEMU ARM64; no networking or phone access.
A breakpoint at the PE entry proves execution, not Microsoft UI or phone success.
Requires a prebuilt host-only DavinciWindowsBootSmoke.efi and external AAVMF.
"""
import argparse, hashlib, importlib.util, json, re, socket, subprocess, time, struct, uuid, zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent

def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def run(a):
    repo=HERE.parents[1]
    out=a.output.resolve()
    if out.is_relative_to(repo): raise ValueError('Private carrier must remain outside Git')
    out.mkdir(parents=True,exist_ok=False)
    image=a.fat.read_bytes()
    files=module('target_verify', HERE/'verify_target_a.py').fat_files(image)
    pe=files['EFI/Microsoft/Boot/bootmgfw.efi']
    fat=module('target_fat',HERE/'fat32.py')
    carrier=out/'carrier.img'
    if a.gpt_reference:
        files['EFI/Boot/bootaa64.efi']=a.efi.read_bytes()
        files['TEST/use-outer-fs.flag']=b'host-reference-only'
        carrier_data=module('target_gpt',HERE/'ram_gpt.py').virtual_gpt(fat.create(files))
    else:
        fat.SECTORS=131072
        carrier_data=fat.create({'EFI/BOOT/BOOTAA64.EFI':a.efi.read_bytes(),'TEST/verified-ram-disk.img':module('target_gpt',HERE/'ram_gpt.py').virtual_gpt(image)})
    # Avoid transiently writing 64 MiB of zeroes on small execution disks.
    with carrier.open('xb') as f:
        f.truncate(len(carrier_data))
        for offset in range(0,len(carrier_data),1024*1024):
            chunk=carrier_data[offset:offset+1024*1024]
            if any(chunk):f.seek(offset);f.write(chunk)
    del carrier_data
    subprocess.run(['fallocate','--dig-holes',str(carrier)],check=True)
    with socket.socket() as port:
        port.bind(('127.0.0.1',0));gdbport=port.getsockname()[1]
    command=[str(a.qemu),'-L',str(a.rom_dir),'-machine','virt,gic-version=3','-cpu','max','-m','1024','-accel','tcg',
             '-bios',str(a.firmware),'-device','ramfb','-drive',f'if=none,id=target,format=raw,readonly=on,file={carrier}',
             '-device','virtio-blk-device,drive=target','-nic','none','-display','none','-serial',f'file:{out}/serial.log',
             '-qmp',f'unix:{out}/qmp.sock,server=on,wait=off','-gdb',f'tcp:127.0.0.1:{gdbport}','-S','-no-reboot']
    (out/'COMMAND.json').write_text(json.dumps(command,indent=2)+'\n')
    result={'host':'QEMU ARM64, not phone','fat32_sha256':hashlib.sha256(image).hexdigest(),
            'bootmgfw_sha256':hashlib.sha256(pe).hexdigest(),'entry_reached':False,
            'microsoft_ui_automatically_verified':False,'physical_test_ready':False}
    trace=[];s=None
    def exact(n):
        b=b''
        while len(b)<n:
            part=s.recv(n-len(b))
            if not part:raise EOFError('Debugger disconnected')
            b+=part
        return b
    def packet():
        while exact(1)!=b'$':pass
        b=bytearray()
        while True:
            c=exact(1)
            if c==b'#':break
            b+=c
        check=exact(2)
        if int(check,16)!=sum(b)%256:raise ValueError('RSP checksum mismatch')
        s.sendall(b'+');trace.append(['recv',bytes(b).decode(errors='replace')]);return bytes(b)
    def send(data,reply=True):
        data=data.encode();trace.append(['send',data.decode()])
        s.sendall(b'$'+data+b'#'+f'{sum(data)%256:02x}'.encode())
        return packet() if reply else None
    with (out/'qemu.log').open('wb') as log:
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+90
            while True:
                try:s=socket.create_connection(('127.0.0.1',gdbport),timeout=1);break
                except OSError:
                    if proc.poll() is not None or time.monotonic()>deadline:raise
                    time.sleep(.1)
            s.settimeout(15);send('qSupported:multiprocess+;qXfer:features:read+');send('?');send('c',False)
            while time.monotonic()<deadline:
                text=(out/'serial.log').read_text(errors='replace') if (out/'serial.log').exists() else ''
                m=re.search(r'HOST_SMOKE ENTRY_ADDRESS=([0-9a-fA-F]+)',text)
                if m:break
                time.sleep(.05)
            else:raise TimeoutError('PE entry address not reported')
            entry=int(m.group(1),16);s.sendall(b'\x03');packet()
            if send(f'Z1,{entry:x},4')!=b'OK':raise RuntimeError('Entry breakpoint rejected')
            send('c',False);stop=packet();registers=send('g')
            pc=int.from_bytes(bytes.fromhex(registers.decode())[256:264],'little')
            result.update(entry=hex(entry),pc=hex(pc),entry_reached=pc==entry,stop_reply=stop.decode())
            if pc!=entry:raise RuntimeError('Stop PC is not PE entry')
            send(f'z1,{entry:x},4');send('c',False)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                text=(out/'serial.log').read_text(errors='replace')
                m=re.search(r'HOST_SMOKE START_RETURN=([0-9a-fA-F]+)',text)
                if m:
                    result['start_return']='0x'+m.group(1);break
                time.sleep(.1)
            # Observation only: retain screenshot without claiming a Microsoft UI.
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as q:
                q.settimeout(5);q.connect(str(out/'qmp.sock'));f=q.makefile('rwb',buffering=0);f.readline()
                def qmp(obj):
                    f.write(json.dumps(obj).encode()+b'\n')
                    while True:
                        r=json.loads(f.readline())
                        if 'return' in r or 'error' in r:return r
                qmp({'execute':'qmp_capabilities'})
                result['screendump']=qmp({'execute':'screendump','arguments':{'filename':str(out/'screen.ppm')}})
                qmp({'execute':'quit'})
        except Exception as e:
            result['error']=repr(e)
            raise
        finally:
            if s:s.close()
            if proc.poll() is None:proc.terminate()
            proc.wait(timeout=10)
            (out/'RSP_TRACE.json').write_text(json.dumps(trace,indent=2)+'\n')
            (out/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('qemu','firmware','rom-dir','efi','fat','output'):p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--gpt-reference',action='store_true',help='PC-only GPT/PartitionDxe reference instead of shared RAM provider')
    run(p.parse_args())
