"""Apply the validated offline IPS locally, refusing modified or aliased inputs."""
import argparse, hashlib
from io import BytesIO
from pathlib import Path
from build import BASE_SHA256, PATCH_SHA256, OUTPUT_SHA256, load_ips, require, write_new

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('--patch',type=Path,required=True)
    parser.add_argument('--lazy-ips',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(args.output.resolve()!=args.original.resolve(),'Input and output must differ')
    if args.output.exists():
        require(not args.output.samefile(args.original),'Input/output hardlink alias')
    original=args.original.read_bytes()
    require(len(original)==0x200000 and hashlib.sha256(original).hexdigest()==BASE_SHA256,'Use the unmodified original Japanese ROM; EZFlash/Perfect Crystal inputs are not accepted')
    patch=args.patch.read_bytes()
    ips=load_ips(args.lazy_ips)
    require(hashlib.sha256(patch).hexdigest()==PATCH_SHA256,'IPS hash mismatch')
    target=BytesIO(original)
    for record in ips.read_patch(BytesIO(patch)):ips.apply_patch_line(target,record)
    output=target.getvalue()
    require(hashlib.sha256(output).hexdigest()==OUTPUT_SHA256,'Patched ROM hash mismatch')
    write_new(args.output,output)
    print('Created:',args.output.name)
    print('SHA256:',OUTPUT_SHA256)

if __name__=='__main__':main()
