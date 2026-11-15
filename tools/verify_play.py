"""Local UI and battery-save round trips on a synthetic (not user) save."""
from pathlib import Path
from io import BytesIO
import hashlib,json,sys,argparse
from pyboy import PyBoy
parser=argparse.ArgumentParser()
parser.add_argument('--work-dir',type=Path,default=Path(__file__).resolve().parents[1]/'build')
parser.add_argument('--fixture',type=Path,required=True)
args=parser.parse_args()
HERE=args.work_dir.resolve()
ROM=(HERE/'candidate.gbc').read_bytes()
from build import OUTPUT_SHA256
assert hashlib.sha256(ROM).hexdigest()==OUTPUT_SHA256, 'Unsupported ROM'
OLD=args.fixture.read_bytes()
assert len(OLD)==65536, 'Expected a private 64 KiB fixture'

def fixture(gender,location):
    ram=bytearray(OLD[:32768])
    ram[0x7f20:0x7f27]=OLD[0x8000:0x8007]
    ram[0x7f20]=gender;ram[0x7f27:0x7f29]=b'\0\0'
    return bytes(ram)

def start(ram):
    stream=BytesIO(ram)
    em=PyBoy(BytesIO(ROM),ram_file=stream,window='null',sound_emulated=False)
    em.set_emulation_speed(0)
    tick(em,600);press(em,'start');press(em,'a');press(em,'a');press(em,'a');tick(em,200)
    return em,stream

def tick(em,n):em.tick(n,render=True,sound=False)
def press(em,key,n=8,after=120):
    em.button_press(key);tick(em,n);em.button_release(key);tick(em,after)

def battery(em):
    result=bytearray();em.memory[0]=10
    for bank in range(4):
        em.memory[0x4000]=bank;result.extend(em.memory[0xa000:0xc000])
    em.memory[0]=0
    return bytes(result)

reports=[]
for gender in (0,1):
    for location in ('home','pcc'):
        em,stream=start(fixture(gender,location))
        original_boxes=battery(em)[0x4000:0x7200]
        if location=='pcc':
            assert ROM[0x97ff0:0x97ff6]==bytes(6)
            for i,value in enumerate([0x3c,11,2,14,28,0x90]):
                em.memory[0x25,0x7ff0+i]=value
            entered=[]
            def start_warp(_):
                if not entered:
                    entered.append(True)
                    em.memory[1,0xd428:0xd42d]=[1,1,0x25,0xf0,0x7f]
                    em.memory[1,0xd42d]=0
            entry=ROM.index(bytes.fromhex('cdf96dfa28d4'),0x94000,0x98000)%0x4000+0x4000
            em.hook_register(0x25,entry,start_warp,None)
            tick(em,240)
            em.hook_deregister(0x25,entry)
            em.screen.image.save(str(HERE/f'pcc_gender{gender}_warp.png'))
            assert entered and em.memory[1,0xdc7b:0xdc7f]==[11,2,28,14],(entered,em.memory[1,0xdc7b:0xdc7f],hex(em.register_file.PC),em.memory[1,0xd428:0xd42e])
            press(em,'up',16,after=240)
            em.screen.image.save(str(HERE/f'pcc_gender{gender}_entered.png'))
            assert em.memory[1,0xdc7b:0xdc7d]==[11,20],em.memory[1,0xdc7b:0xdc7f]
        assert em.memory[1,0xd463]==gender
        assert em.memory[1,0xd46a:0xd46c]==[0,0]
        start_pos=em.memory[1,0xdc7d:0xdc7f]
        press(em,'right',24);right_pos=em.memory[1,0xdc7d:0xdc7f]
        press(em,'left',24);left_pos=em.memory[1,0xdc7d:0xdc7f]
        em.screen.image.save(str(HERE/f'{location}_gender{gender}_walk.png'))
        assert start_pos!=right_pos or right_pos!=left_pos,(location,start_pos,right_pos,left_pos)
        # The fixture has a single test party member; open the normal menu.
        press(em,'start')
        em.screen.image.save(str(HERE/f'{location}_gender{gender}_menu.png'))
        em.save_state(open(HERE/f'{location}_gender{gender}_menu.state','wb'))
        for _ in range(3):press(em,'down')
        em.screen.image.save(str(HERE/f'{location}_gender{gender}_save_selected.png'))
        press(em,'a');press(em,'a');press(em,'a');tick(em,240)
        em.screen.image.save(str(HERE/f'{location}_gender{gender}_saved.png'))
        em.save_state(open(HERE/f'{location}_gender{gender}_saved.state','wb'))
        saved=battery(em)
        assert saved!=fixture(gender,location)[:32768],'Menu did not write a save'
        (HERE/f'gender{gender}_saved.ram').write_bytes(saved)
        expected_map=em.memory[1,0xdc7b:0xdc7f]
        expected_party=em.memory[1,0xdc9d:0xde0d]
        expected_identity=em.memory[1,0xd48c:0xd494]
        assert saved[0x4000:0x7200]==original_boxes,'Box storage changed'
        assert int.from_bytes(saved[0x2d0d:0x2d0f],'little')==sum(saved[0x2009:0x2ae3])&65535
        em.stop(save=False)
        resumed,_=start(saved)
        resumed.screen.image.save(str(HERE/f'{location}_gender{gender}_resumed.png'))
        assert resumed.memory[1,0xd463]==gender
        assert resumed.memory[1,0xdc7b:0xdc7f]==expected_map,(location,expected_map,resumed.memory[1,0xdc7b:0xdc7f])
        assert resumed.memory[1,0xdc9d:0xde0d]==expected_party
        assert resumed.memory[1,0xd48c:0xd494]==expected_identity
        resumed.screen.image.save(str(HERE/f'{location}_gender{gender}_resumed.png'))
        resumed.stop(save=False)
        reports.append(dict(gender=gender,location=location,start_position=start_pos,right_position=right_pos,left_position=left_pos,party_count=expected_party[0],menu_save_and_battery_restart=True,identity_party_and_boxes_preserved=True))
(HERE/'play_progress.json').write_text(json.dumps(reports,indent=2)+'\n')
(HERE/'play_results.json').write_text(json.dumps({'passed':True,'rom_sha256':hashlib.sha256(ROM).hexdigest(),'cases':reports,'hardware_tested':False},indent=2)+'\n')
print(json.dumps(reports,indent=2))
