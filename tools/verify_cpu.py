"""Exercise assembled SRAM, RTC, and relocated Crystal data on the SM83 CPU."""
from pathlib import Path
from io import BytesIO
import hashlib, json, argparse
from pyboy import PyBoy

parser=argparse.ArgumentParser()
parser.add_argument('--work-dir',type=Path,default=Path(__file__).resolve().parents[1]/'build')
HERE=parser.parse_args().work_dir.resolve()
rom=(HERE/'candidate.gbc').read_bytes()
from build import OUTPUT_SHA256
assert hashlib.sha256(rom).hexdigest()==OUTPUT_SHA256, 'Unsupported ROM'
em=PyBoy(BytesIO(rom),window='null',sound_emulated=False)
em.tick(600,render=False,sound=False)
r=em.register_file
em.memory[0xffff]=em.memory[0xff0f]=0
em.memory[0xff70]=1
em.memory[0xff80:0xff83]=[0xc3,0x80,0xff]
returned=[]
def finish(_):
    returned.append((r.A,r.F,(r.B<<8)|r.C,(r.D<<8)|r.E,r.HL,r.SP))
    r.PC=0xff80
em.hook_register(0,0x100,finish,None)

def call(bank,pc,a=0,f=0xb0):
    returned.clear()
    em.memory[0x2000]=em.memory[0xff9d]=bank or 1
    r.A=a;r.F=f;r.B=0x12;r.C=0x34;r.D=0x56;r.E=0x78;r.HL=0x9abc
    r.SP=0xcffe;em.memory[0xcffe:0xd000]=[0,1];r.PC=pc
    for _ in range(60):
        em.tick(1,render=False,sound=False)
        if returned:break
    assert len(returned)==1, (bank,pc,len(returned),r.PC)
    assert em.memory[0xff9d]==(bank or 1),'ROM bank not restored'
    return returned[0]

def read_sram():
    data=bytearray()
    em.memory[0]=10
    for bank in range(4):
        em.memory[0x4000]=bank;data.extend(em.memory[0xa000:0xc000])
    em.memory[0]=0
    return bytes(data)

em.memory[0]=10
for bank in range(4):
    em.memory[0x4000]=bank
    em.memory[0xa000:0xc000]=[(i+bank*37)&255 for i in range(8192)]
em.memory[0]=0
baseline=read_sram()
count=0
for a in range(256):
    for f in (0,0xf0):
        actual=call(0,0x2f9d,a,f)
        assert actual==(a,f,0x1234,0x5678,0x9abc,0xd000),actual
        if a<4:
            assert em.memory[0xa000]==a*37
            em.memory[0xa000]=0x91
            assert em.memory[0xa000]==0x91
            em.memory[0xa000]=a*37
        elif not 8<=a<=12:
            assert em.memory[0xa000]==255
            em.memory[0xa000:0xc000]=[0x91]*8192
        closed=call(0,0x2fad,a,f)
        assert closed==(a,f,0x1234,0x5678,0x9abc,0xd000)
        assert em.memory[0xa000]==255
        count+=1
assert read_sram()==baseline, 'Rejected banks changed battery SRAM'
for bank in range(1,128):
    assert call(bank,0x2f9d,3)==(3,0xb0,0x1234,0x5678,0x9abc,0xd000)
    assert em.memory[0x4000:0x4010]==list(rom[bank*0x4000:bank*0x4000+16]),'Hardware ROM bank not restored'
    call(bank,0x2fad)

# RTC halt + registers 8..12 are accessible through the guarded routine.
for reg,value in ((12,0x40),(8,42),(9,17),(10,13),(11,123)):
    call(0,0x2f9d,reg);em.memory[0xa000]=value;call(0,0x2fad)
for reg,value in ((8,42),(9,17),(10,13),(11,123),(12,0x40)):
    call(0,0x2f9d,reg)
    assert em.memory[0xa000]==value,(reg,em.memory[0xa000])
    call(0,0x2fad)

for gender in (0,1):
    before=read_sram()
    data=[gender,0x32,0x1,0x12,0x34,0x56,0x78,0,0]
    em.memory[0xd463:0xd46c]=data
    call(5,0x5068)
    after=read_sram()
    expected=bytearray(before);expected[0x7f20:0x7f29]=bytes(data)
    assert after==expected,'Crystal data write escaped reserved area'
    em.memory[0xd463:0xd46c]=[255]*9
    call(5,0x5087)
    assert em.memory[0xd463:0xd46c]==data,'Crystal data/gender restore failed'
    assert read_sram()==after,'Load mutated save'

for f in (0,0xf0):
    status=call(0x41,0x6397,0xff,f)
    assert status[0]==0 and status[2]&255==0 and not status[1]&0x10
    em.memory[0xc2dd]=255
    call(0x5c,0x4918,0xff,f)
    assert em.memory[0xc2dd]==0
    em.memory[0xc2dd]=255
    call(0x5c,0x4816,0xff,f)
    assert em.memory[0xc2dd]==0
for gender in (0,1):
    data=[gender,18,2,1,2,3,4,0,0]
    em.memory[0xd463:0xd46c]=data
    call(5,0x4c6b)
    assert read_sram()[0x7f20:0x7f29]==bytes(data), 'New-save initialization lost Crystal data'
report={'cpu':'PyBoy SM83, standard MBC3 selected by 32 KiB header','bank_and_flags_cases':count,'rom_bank_restore_cases':127,'rejected_bank_write_isolation':True,'rtc_registers_checked':[8,9,10,11,12],'genders_checked':[0,1],'crystal_data_only_writes_reserved_9_bytes':True,'mobile_status_always_unconfigured':True,'rom_sha256':hashlib.sha256(rom).hexdigest(),'passed':True}
(HERE/'cpu_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
em.stop(save=False)
