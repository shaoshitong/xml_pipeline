import java.lang.instrument.*;
import java.security.ProtectionDomain;
import jdk.internal.org.objectweb.asm.*;
import jdk.internal.org.objectweb.asm.tree.*;
public class PlantumlEngineDrawAgentV1 {
 public static int patches=0;
 public static String method="";
 public static void premain(String arguments,Instrumentation instrumentation){instrumentation.addTransformer(new ClassFileTransformer(){public byte[] transform(ClassLoader loader,String name,Class<?> type,ProtectionDomain domain,byte[] bytes){
  if(!name.equals("net/sourceforge/plantuml/svek/SvekResult"))return null;
  try{ClassNode c=new ClassNode();new ClassReader(bytes).accept(c,0);int n=0;for(MethodNode m:c.methods){if(!m.name.equals("drawU"))continue;for(AbstractInsnNode i:m.instructions.toArray())if(i instanceof MethodInsnNode){MethodInsnNode invoke=(MethodInsnNode)i;if(invoke.owner.equals("net/sourceforge/plantuml/svek/IEntityImage")&&invoke.name.equals("drawU")){
   AbstractInsnNode prior=i.getPrevious();int slot=-1;for(int limit=0;prior!=null&&limit<50;limit++,prior=prior.getPrevious())if(prior instanceof MethodInsnNode){MethodInsnNode getter=(MethodInsnNode)prior;if(getter.owner.equals("net/sourceforge/plantuml/svek/SvekNode")&&getter.name.equals("getImage")){AbstractInsnNode load=prior.getPrevious();while(load instanceof LabelNode||load instanceof LineNumberNode||load instanceof FrameNode)load=load.getPrevious();if(!(load instanceof VarInsnNode)||load.getOpcode()!=Opcodes.ALOAD)throw new IllegalStateException("unexpected_source_node_local_pattern");slot=((VarInsnNode)load).var;break;}}
   if(slot<0)throw new IllegalStateException("missing_actual_source_node_local");m.instructions.insertBefore(i,new VarInsnNode(Opcodes.ALOAD,slot));m.instructions.set(i,new MethodInsnNode(Opcodes.INVOKESTATIC,"PlantumlEnginePaintHookV1","draw","(Lnet/sourceforge/plantuml/svek/IEntityImage;Lnet/sourceforge/plantuml/klimt/drawing/UGraphic;Lnet/sourceforge/plantuml/svek/SvekNode;)V",false));method=m.name+m.desc+":nodeLocal="+slot;n++;
  }}}
  if(n!=1)throw new IllegalStateException("expected_exactly_one_verified_draw_site:"+n);ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(writer);patches=n;return writer.toByteArray();}catch(Throwable e){throw new RuntimeException("source_nonpaint_owner_instrumentation_failed",e);}
 }});}
}
