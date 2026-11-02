import java.nio.charset.StandardCharsets;
import java.util.*;
import java.io.*;
import java.lang.reflect.*;
import net.sourceforge.plantuml.klimt.*;
import net.sourceforge.plantuml.klimt.shape.*;
import net.sourceforge.plantuml.klimt.geom.*;
import net.sourceforge.plantuml.klimt.font.*;
import net.sourceforge.plantuml.klimt.color.*;
import net.sourceforge.plantuml.klimt.drawing.*;
import net.sourceforge.plantuml.svek.*;
import java.nio.file.*;
import net.sourceforge.plantuml.FileFormat;
import net.sourceforge.plantuml.FileFormatOption;
import net.sourceforge.plantuml.SourceStringReader;
import net.sourceforge.plantuml.core.Diagram;
import net.atmp.CucaDiagram;
import net.sourceforge.plantuml.abel.Entity;
import net.sourceforge.plantuml.abel.Link;
public class PlantumlEngineSceneV7 {
 static String q(Object x){if(x==null)return "null";String s=x.toString(),b="\"";for(char c:s.toCharArray()){if(c=='\\'||c=='\"')b+="\\"+c;else if(c<32)b+=String.format("\\u%04x",(int)c);else b+=c;}return b+"\"";}
 static String key(Entity e){try{byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(e.getQuark().getQualifiedName().getBytes(StandardCharsets.UTF_8));String s="own_";for(int i=0;i<16;i++)s+=String.format("%02x",b[i]);return s;}catch(Exception x){throw new RuntimeException(x);}}
 static String linkkey(Link l){try{String text=l.getUid()+"|"+l.idCommentForSvg()+"|"+(l.getLocation()==null?"":l.getLocation().getPosition());byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));String s="rel_";for(int i=0;i<16;i++)s+=String.format("%02x",b[i]);return s;}catch(Exception x){throw new RuntimeException(x);}}
 static String entity(Entity e){return "{\"original_uid\":"+q(e.getUid())+",\"uid\":"+q(key(e))+",\"name\":"+q(e.getName())+",\"qualified_name\":"+q(e.getQuark().getQualifiedName())+",\"display\":"+q(e.getDisplay())+",\"parent_uid\":"+q(e.getParentContainer()==null?null:key(e.getParentContainer()))+",\"is_group\":"+e.isGroup()+",\"kind\":"+q(e.isGroup()?e.getGroupType():e.getLeafType())+",\"hidden\":"+e.isHidden()+",\"removed\":"+e.isRemoved()+",\"source_line\":"+(e.getLocation()==null?"null":e.getLocation().getPosition())+"}";}
 static Diagram diagram(String source){SourceStringReader reader=new SourceStringReader(source);if(reader.getBlocks().size()!=1)throw new IllegalArgumentException("requires_single_diagram");return reader.getBlocks().get(0).getDiagram();}
 // Keep actual parsed object references: nested State rendering drains its
 // parent Cuca link list into nested diagrams during one paint pass.
 static final Map<Diagram,List<List<?>>> semanticObjects=new IdentityHashMap<>();
 static String model(Diagram d){List<String> nodes=new ArrayList<>(),groups=new ArrayList<>(),links=new ArrayList<>();
  if(d instanceof CucaDiagram){CucaDiagram c=(CucaDiagram)d;
   List<List<?>> captured=semanticObjects.get(d);if(captured==null){List<Entity> ns=new ArrayList<>(),gs=new ArrayList<>();for(Entity e:c.leafs())ns.add(e);for(Entity e:c.groups())gs.add(e);captured=Arrays.asList(ns,gs,new ArrayList<Link>(c.getLinks()));semanticObjects.put(d,captured);}
   for(Object o:captured.get(0))nodes.add(entity((Entity)o));for(Object o:captured.get(1))groups.add(entity((Entity)o));for(Object item:captured.get(2)){Link l=(Link)item;links.add("{\"original_uid\":"+q(l.getUid())+",\"svg_id\":"+q(l.idCommentForSvg())+",\"opale\":"+l.isOpale()+",\"uid\":"+q(linkkey(l))+",\"entity1_uid\":"+q(key(l.getEntity1()))+",\"entity2_uid\":"+q(key(l.getEntity2()))+",\"entity1_name\":"+q(l.getEntity1().getQuark().getQualifiedName())+",\"entity2_name\":"+q(l.getEntity2().getQuark().getQualifiedName())+",\"port1\":"+q(l.getPortName1())+",\"port2\":"+q(l.getPortName2())+",\"decor1\":"+q(l.getType().getDecor1())+",\"decor2\":"+q(l.getType().getDecor2())+",\"label\":"+q(l.getLabel())+",\"invisible\":"+l.isInvis()+",\"hidden\":"+l.isHidden()+",\"removed\":"+l.isRemoved()+",\"constraint\":"+l.isConstraint()+",\"inverted\":"+l.isInverted()+",\"source_line\":"+(l.getLocation()==null?"null":l.getLocation().getPosition())+"}");}}
  return "{\"schema\":\"plantuml_engine_scene_semantic_ir_v1\",\"diagram_class\":"+q(d.getClass().getName())+",\"description\":"+q(d.getDescription())+",\"cuca_supported\":"+(d instanceof CucaDiagram)+",\"entities\":["+String.join(",",nodes)+"],\"groups\":["+String.join(",",groups)+"],\"links\":["+String.join(",",links)+"]}";
 }
 public static void main(String[] args)throws Exception{
  if(args.length==1&&args[0].equals("models")){BufferedReader br=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));String line;while((line=br.readLine())!=null){try{String src=new String(Base64.getDecoder().decode(line),StandardCharsets.UTF_8);System.out.println(model(diagram(src)));}catch(Throwable e){System.out.println("{\"error\":"+q(e.toString())+"}");}}return;}
  String source=new String(System.in.readAllBytes(),StandardCharsets.UTF_8);PlantumlEnginePaintHookV4.enabled=false;Diagram pristine=diagram(source);String before=model(pristine);Files.writeString(Path.of("engine_before.json"),before,StandardCharsets.UTF_8);
  if(!(pristine instanceof CucaDiagram)){Files.writeString(Path.of("engine_ir.json"),before,StandardCharsets.UTF_8);System.out.println(before);return;}
  try(OutputStream out=Files.newOutputStream(Path.of("source.original.png"))){pristine.exportDiagram(out,0,new FileFormatOption(FileFormat.PNG));}
  String pristineIR=model(pristine);Files.writeString(Path.of("engine_pristine.json"),pristineIR,StandardCharsets.UTF_8);
  Diagram d=diagram(source);if(!model(d).equals(before))throw new IllegalStateException("fresh_source_model_before_layout_differs");PlantumlEnginePaintHookV4.expectedDiagram=d;PlantumlEnginePaintHookV4.enabled=true;
  try(OutputStream out=Files.newOutputStream(Path.of("source.png"))){d.exportDiagram(out,0,new FileFormatOption(FileFormat.PNG));}
  String ir=model(d);Files.writeString(Path.of("engine_ir.json"),ir,StandardCharsets.UTF_8);Files.writeString(Path.of("engine_after_png.json"),ir,StandardCharsets.UTF_8);if(!ir.equals(pristineIR))throw new IllegalStateException("source_dual_painter_changed_same_phase_engine_IR");
  if(PlantumlEngineDrawAgentV4.patches!=3)throw new IllegalStateException("owner_and_dual_draw_hooks_not_applied");if(!Files.exists(Path.of("source.svg")))throw new IllegalStateException("no_actual_main_Diagram_dual_paint_stream");Files.writeString(Path.of("ownership_instrumentation.json"),PlantumlEnginePaintHookV4.report(),StandardCharsets.UTF_8);System.out.println(ir);
 }
}
