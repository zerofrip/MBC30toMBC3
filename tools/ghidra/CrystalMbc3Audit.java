import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;

public class CrystalMbc3Audit extends GhidraScript {
    public void run() throws Exception {
        try (PrintWriter out = new PrintWriter(getScriptArgs()[0])) {
            out.println("Language: " + currentProgram.getLanguageID());
            for (int[] range : new int[][] {{0,0x2f9d,0x2fb8},{0,0x3f7f,0x3f9f},{5,0x5068,0x50a6},{0x41,0x6397,0x639a},{0x5c,0x4816,0x481b},{0x5c,0x4918,0x491d}}) {
                MemoryBlock block=currentProgram.getMemory().getBlock("rom"+range[0]);
                if (block==null) throw new IllegalStateException("Missing ROM bank " + range[0]);
                Address at=block.getStart().add(range[1]-(range[0]==0?0:0x4000));
                disassemble(at);
                while (at.getOffset()<block.getStart().getOffset()+range[2]-(range[0]==0?0:0x4000)) {
                    disassemble(at);
                    var ins=currentProgram.getListing().getInstructionAt(at);
                    if (ins==null) throw new IllegalStateException("Undecoded " + at);
                    out.println(range[0]+":"+at+" "+ins);
                    at=at.add(ins.getLength());
                }
            }
        }
        println("MBC3 audit disassembly saved locally");
    }
}
