#!/usr/bin/env python3
"""Inspect supplied Windows files only. No driver installation/INF editing/registry access."""
import argparse,hashlib,importlib.util,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('windows_prepare',ROOT/'Resources/Windows/davinci/prepare_windows.py')
w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
def inspect(sys_path,inf_path):
 sys_path=sys_path.resolve(strict=True);inf_path=inf_path.resolve(strict=True)
 raw=inf_path.read_bytes()
 text=raw.decode('utf-16') if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else raw.decode('utf-8-sig')
 lines=[line.split(';',1)[0].strip() for line in text.splitlines()]
 active='\n'.join(lines)
 relevant=[line for line in lines if re.search(r'(?i)QCOM24A5|PNP0D40|ACPI0012|DriverVer|CatalogFile|AddService|ServiceBinary|StartType|LoadOrderGroup|Include\s*=|Needs\s*=',line)]
 return {'sys':{'sha256':hashlib.sha256(sys_path.read_bytes()).hexdigest(),**w.arm64_pe(sys_path)},
 'inf_sha256':hashlib.sha256(raw).hexdigest(),
 'qcom24a5_text_in_active_inf':bool(re.search(r'(?i)ACPI\\QCOM24A5\b',active)),
 'relevant_active_lines':relevant,'signature_and_catalog_chain_verified':False,
 'service_registry_boot_start_verified':False,'sm7150_compatibility_verified':False,
 'deployment_ready':False,
 'required_evidence':['Exact Windows build and matching SYS/INF/CAT signature validation',
 'Selected ARM64 model/INF sections and service registry Start=0 plus dependencies',
 'SM7150 host-controller, PHY/clocks/reset/power resource contract',
 'ACPI _CRS/_CCA and IORT stream mapping, DMA ownership/coherency',
 'Real UEFI read-only Block I/O and GPT then a Windows kernel storage test']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--sys',dest='sys_path',required=True,type=Path);p.add_argument('--inf',required=True,type=Path);a=p.parse_args()
 print(json.dumps(inspect(a.sys_path,a.inf),indent=2))
