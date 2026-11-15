"""Build a local, original-JP-only MBC3 offline patch; never uploads inputs."""
from pathlib import Path
from io import BytesIO
import argparse, hashlib, json, re, subprocess, sys, tempfile

ROOT=Path(__file__).resolve().parents[1]
BASE_SHA256='136ada06cb68656b7de475fa4b278d37dbeff8f5257e7dfdf7f4a4aec19a90f3'
PATCH_SHA256='5e497d01fbe5037de88e3986e34498bf5e5d46b6a65bd4cb77df4bba63e00c1a'
OUTPUT_SHA256='9122ef3a80c7ab15ac4ece478a17d03f79aca3a4ce1e35fbd6c8650f8fef29ce'

def load_ips(folder):
    require((folder/'lazy_ips/patch/ips.py').is_file(), 'Expected lazy_ips checkout')
    sys.path.insert(0,str(folder.resolve()))
    from lazy_ips.patch import ips
    return ips

def require(condition, message):
    if not condition: raise ValueError(message)

def write_new(path, data):
    require(not path.is_symlink(), 'Refusing symlink output: '+path.name)
    if path.exists():
        require(path.read_bytes()==data, 'Existing different output: '+path.name)
        return
    with path.open('xb') as f: f.write(data)

def build(args, scratch):
    ips=load_ips(args.lazy_ips)
    require((args.gb_asm_tools/'tools/mapreader.py').is_file(), 'Expected gb-asm-tools checkout')
    sys.path.insert(0,str((args.gb_asm_tools/'tools').resolve()))
    from mapreader import MapReader
    original=args.rom.read_bytes()
    require(len(original)==0x200000 and hashlib.sha256(original).hexdigest()=='136ada06cb68656b7de475fa4b278d37dbeff8f5257e7dfdf7f4a4aec19a90f3', 'Unsupported original ROM')
    subprocess.run([args.rgbasm,'-o',str(scratch/'patch.o'),str(ROOT/'src/patch.asm')],check=True)
    subprocess.run([args.rgblink,'-o',str(scratch/'overlay.bin'),'-m',str(scratch/'patch.map'),'-n',str(scratch/'patch.sym'),str(scratch/'patch.o')],check=True)
    # gb-asm-tools MapReader understands current RGBDS bank headings.
    lines=[]
    for line in (scratch/'patch.map').read_text().splitlines():
        match=re.match(r'ROM Bank #(\d+)',line)
        if match:
            bank=int(match[1]); line=f'ROM{0 if bank==0 else "X"} bank #{bank}:'
        lines.append(line)
    reader=MapReader(bank_data={});reader.read_map_data(lines)
    overlay=(scratch/'overlay.bin').read_bytes()
    result=bytearray(original); sections=[]
    for kind in ('ROM0 bank','ROMX bank'):
        for bank,meta in reader.bank_data.get(kind,{}).items():
            for section in meta['sections']:
                begin=section['beg']+(bank-1)*0x4000 if bank else section['beg']
                end=begin+section['end']-section['beg']+1
                result[begin:end]=overlay[begin:end]
                sections.append(dict(name=section['name'],offset=begin,length=end-begin))
    require(len(sections)==7,'Unexpected assembled section count')
    require(original[0x3f7f:0x4000]==bytes(0x81),'Injected routine space is not empty')
    result[0x149]=3 # 32 KiB SRAM; keep type $10 (MBC3 + timer + RAM + battery).
    result[0x14d]=(-sum(result[0x134:0x14d])-25)&255
    checksum=(sum(result[:0x14e])+sum(result[0x150:]))&65535
    result[0x14e:0x150]=checksum.to_bytes(2,'big')
    patch=bytearray(b'PATCH');i=0;record_count=0
    while i<len(result):
        if result[i]==original[i]: i+=1;continue
        begin=i
        while i<len(result) and result[i]!=original[i] and i-begin<32767: i+=1
        patch+=begin.to_bytes(3,'big')+(i-begin).to_bytes(2,'big')+result[begin:i]
        record_count+=1
    patch+=b'EOF'
    reapplied=BytesIO(original)
    for line in ips.read_patch(BytesIO(patch)): ips.apply_patch_line(reapplied,line)
    require(reapplied.getvalue()==result,'lazy_ips round trip failed')
    require(hashlib.sha256(result).hexdigest()==OUTPUT_SHA256, 'Unexpected output ROM hash')
    require(hashlib.sha256(patch).hexdigest()==PATCH_SHA256, 'Unexpected IPS hash')
    manifest={'base_sha256':hashlib.sha256(original).hexdigest(),'rom_sha256':hashlib.sha256(result).hexdigest(),'ips_sha256':hashlib.sha256(patch).hexdigest(),'ips_bytes':len(patch),'records':record_count,'sections':sections,'status':'known artifact reproduced; hardware not tested','hardware_tested':False,'mobile_adapter_supported':False}
    write_new(args.out_dir/'candidate.gbc',result)
    write_new(args.out_dir/'candidate.ips',patch)
    write_new(args.out_dir/'candidate.json',(json.dumps(manifest,indent=2)+'\n').encode())
    print(json.dumps(manifest,indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--lazy-ips',type=Path,required=True)
    parser.add_argument('--gb-asm-tools',type=Path,required=True)
    parser.add_argument('--rgbasm',default='rgbasm')
    parser.add_argument('--rgblink',default='rgblink')
    parser.add_argument('--out-dir',type=Path,default=ROOT/'build')
    args=parser.parse_args()
    original=args.rom.read_bytes()
    require(len(original)==0x200000 and hashlib.sha256(original).hexdigest()==BASE_SHA256, 'Unsupported original ROM')
    args.out_dir.mkdir(parents=True,exist_ok=True)
    for name in ('candidate.gbc','candidate.ips','candidate.json'):
        output=args.out_dir/name
        require(output.resolve()!=args.rom.resolve(),'Input/output alias')
        require(not output.exists() or not output.samefile(args.rom),'Input/output hardlink alias')
    with tempfile.TemporaryDirectory(prefix='mbc3-build-') as directory:
        build(args,Path(directory))

if __name__=='__main__': main()
