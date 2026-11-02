import java.lang.instrument.*;
import java.security.ProtectionDomain;
import jdk.internal.org.objectweb.asm.*;
import jdk.internal.org.objectweb.asm.tree.*;
public class PlantumlEngineDrawAgentV3 {
 public static int patches=0;
 public static String method="";
 public static void premain(String arguments,Instrumentation instrumentation){instrumentation.addTransformer(new ClassFileTransformer(){public byte[] transform(ClassLoader loader,String name,Class<?> type,ProtectionDomain domain,byte[] bytes){
  if(!name.equals("net/sourceforge/plantuml/svek/SvekResult")&&!name.equals("net/sourceforge/plantuml/svek/SvekEdge")&&!name.equals("net/atmp/ImageBuilder"))return null;
  try{ClassNode c=new ClassNode();new ClassReader(bytes).accept(c,0);int n=0;for(MethodNode m:c.methods){
 if(name.equals("net/atmp/ImageBuilder")){
  if(!m.name.equals("createUGraphicPNG")||!m.desc.equals("(DLnet/sourceforge/plantuml/klimt/geom/XDimension2D;Ljava/lang/String;Lnet/sourceforge/plantuml/FileFormat;)Lnet/sourceforge/plantuml/klimt/drawing/UGraphic;"))continue;
  int returns=0;for(AbstractInsnNode i:m.instructions.toArray())if(i.getOpcode()==Opcodes.ARETURN){InsnList call=new InsnList();call.add(new VarInsnNode(Opcodes.ALOAD,3));call.add(new VarInsnNode(Opcodes.DLOAD,1));call.add(new VarInsnNode(Opcodes.ALOAD,0));call.add(new MethodInsnNode(Opcodes.INVOKESTATIC,"PlantumlEnginePaintHookV3","wrapPNG","(Lnet/sourceforge/plantuml/klimt/drawing/UGraphic;Lnet/sourceforge/plantuml/klimt/geom/XDimension2D;DLjava/lang/Object;)Lnet/sourceforge/plantuml/klimt/drawing/UGraphic;",false));m.instructions.insertBefore(i,call);returns++;}if(returns<1)throw new IllegalStateException("missing_source_PNG_graphic_return");n++;continue;
 }
 if(!m.name.equals("drawU"))continue;
  if(name.equals("net/sourceforge/plantuml/svek/SvekEdge")){
   InsnList entry=new InsnList();entry.add(new VarInsnNode(Opcodes.ALOAD,0));entry.add(new VarInsnNode(Opcodes.ALOAD,1));entry.add(new MethodInsnNode(Opcodes.INVOKESTATIC,"PlantumlEnginePaintHookV3","beginEdge","(Lnet/sourceforge/plantuml/svek/SvekEdge;Lnet/sourceforge/plantuml/klimt/drawing/UGraphic;)V",false));m.instructions.insert(entry);
   for(AbstractInsnNode exit:m.instructions.toArray())if(exit.getOpcode()==Opcodes.RETURN){InsnList close=new InsnList();close.add(new VarInsnNode(Opcodes.ALOAD,1));close.add(new MethodInsnNode(Opcodes.INVOKESTATIC,"PlantumlEnginePaintHookV3","endEdge","(Lnet/sourceforge/plantuml/klimt/drawing/UGraphic;)V",false));m.instructions.insertBefore(exit,close);}n++;continue;
  }
  for(AbstractInsnNode i:m.instructions.toArray())if(i instanceof MethodInsnNode){MethodInsnNode invoke=(MethodInsnNode)i;if(invoke.owner.equals("net/sourceforge/plantuml/svek/IEntityImage")&&invoke.name.equals("drawU")){
   AbstractInsnNode prior=i.getPrevious();int slot=-1;for(int limit=0;prior!=null&&limit<50;limit++,prior=prior.getPrevious())if(prior instanceof MethodInsnNode){MethodInsnNode getter=(MethodInsnNode)prior;if(getter.owner.equals("net/sourceforge/plantuml/svek/SvekNode")&&getter.name.equals("getImage")){AbstractInsnNode load=prior.getPrevious();while(load instanceof LabelNode||load instanceof LineNumberNode||load instanceof FrameNode)load=load.getPrevious();if(!(load instanceof VarInsnNode)||load.getOpcode()!=Opcodes.ALOAD)throw new IllegalStateException("unexpected_source_node_local_pattern");slot=((VarInsnNode)load).var;break;}}
   if(slot<0)throw new IllegalStateException("missing_actual_source_node_local");m.instructions.insertBefore(i,new VarInsnNode(Opcodes.ALOAD,slot));m.instructions.set(i,new MethodInsnNode(Opcodes.INVOKESTATIC,"PlantumlEnginePaintHookV3","draw","(Lnet/sourceforge/plantuml/svek/IEntityImage;Lnet/sourceforge/plantuml/klimt/drawing/UGraphic;Lnet/sourceforge/plantuml/svek/SvekNode;)V",false));method=m.name+m.desc+":nodeLocal="+slot;n++;
  }}}
  if(n!=1)throw new IllegalStateException("expected_exactly_one_verified_draw_site:"+n);ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(writer);patches+=n;return writer.toByteArray();}catch(Throwable e){throw new RuntimeException("source_nonpaint_owner_instrumentation_failed",e);}
 }});}
}
