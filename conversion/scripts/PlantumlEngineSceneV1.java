import java.nio.charset.StandardCharsets;
import java.util.*;
import java.io.*;
import java.nio.file.*;
import net.sourceforge.plantuml.FileFormat;
import net.sourceforge.plantuml.FileFormatOption;
import net.sourceforge.plantuml.SourceStringReader;
import net.sourceforge.plantuml.core.Diagram;
import net.atmp.CucaDiagram;
import net.sourceforge.plantuml.abel.Entity;
import net.sourceforge.plantuml.abel.Link;
public class PlantumlEngineSceneV1 {
 static String q(Object x){if(x==null)return "null";String s=x.toString(),b="\"";for(char c:s.toCharArray()){if(c=='\\'||c=='\"')b+="\\"+c;else if(c<32)b+=String.format("\\u%04x",(int)c);else b+=c;}return b+"\"";}
 static String entity(Entity e){return "{\"uid\":"+q(e.getUid())+",\"name\":"+q(e.getName())+",\"qualified_name\":"+q(e.getQuark().getQualifiedName())+",\"display\":"+q(e.getDisplay())+",\"parent_uid\":"+q(e.getParentContainer()==null?null:e.getParentContainer().getUid())+",\"is_group\":"+e.isGroup()+",\"kind\":"+q(e.isGroup()?e.getGroupType():e.getLeafType())+",\"hidden\":"+e.isHidden()+",\"removed\":"+e.isRemoved()+",\"source_line\":"+(e.getLocation()==null?"null":e.getLocation().getPosition())+"}";}
 static Diagram diagram(String source){SourceStringReader reader=new SourceStringReader(source);if(reader.getBlocks().size()!=1)throw new IllegalArgumentException("requires_single_diagram");return reader.getBlocks().get(0).getDiagram();}
 static String model(Diagram d){List<String> nodes=new ArrayList<>(),groups=new ArrayList<>(),links=new ArrayList<>();
  if(d instanceof CucaDiagram){CucaDiagram c=(CucaDiagram)d;for(Entity e:c.leafs())nodes.add(entity(e));for(Entity e:c.groups())groups.add(entity(e));for(Link l:c.getLinks())links.add("{\"uid\":"+q(l.getUid())+",\"entity1_uid\":"+q(l.getEntity1().getUid())+",\"entity2_uid\":"+q(l.getEntity2().getUid())+",\"entity1_name\":"+q(l.getEntity1().getQuark().getQualifiedName())+",\"entity2_name\":"+q(l.getEntity2().getQuark().getQualifiedName())+",\"port1\":"+q(l.getPortName1())+",\"port2\":"+q(l.getPortName2())+",\"decor1\":"+q(l.getType().getDecor1())+",\"decor2\":"+q(l.getType().getDecor2())+",\"label\":"+q(l.getLabel())+",\"invisible\":"+l.isInvis()+",\"hidden\":"+l.isHidden()+",\"removed\":"+l.isRemoved()+",\"constraint\":"+l.isConstraint()+",\"inverted\":"+l.isInverted()+",\"source_line\":"+(l.getLocation()==null?"null":l.getLocation().getPosition())+"}");}
  return "{\"schema\":\"plantuml_engine_scene_semantic_ir_v1\",\"diagram_class\":"+q(d.getClass().getName())+",\"description\":"+q(d.getDescription())+",\"cuca_supported\":"+(d instanceof CucaDiagram)+",\"entities\":["+String.join(",",nodes)+"],\"groups\":["+String.join(",",groups)+"],\"links\":["+String.join(",",links)+"]}";
 }
 public static void main(String[] args)throws Exception{
  if(args.length==1&&args[0].equals("models")){BufferedReader br=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));String line;while((line=br.readLine())!=null){try{String src=new String(Base64.getDecoder().decode(line),StandardCharsets.UTF_8);System.out.println(model(diagram(src)));}catch(Throwable e){System.out.println("{\"error\":"+q(e.toString())+"}");}}return;}
  String source=new String(System.in.readAllBytes(),StandardCharsets.UTF_8);Diagram d=diagram(source);String before=model(d);Files.writeString(Path.of("engine_before.json"),before,StandardCharsets.UTF_8);
  if(!(d instanceof CucaDiagram)){Files.writeString(Path.of("engine_ir.json"),before,StandardCharsets.UTF_8);System.out.println(before);return;}
  try(OutputStream out=Files.newOutputStream(Path.of("source.svg"))){d.exportDiagram(out,0,new FileFormatOption(FileFormat.SVG));}
  String svgIR=model(d);Files.writeString(Path.of("engine_ir.json"),svgIR,StandardCharsets.UTF_8);
  try(OutputStream out=Files.newOutputStream(Path.of("source.png"))){d.exportDiagram(out,0,new FileFormatOption(FileFormat.PNG));}
  String pngIR=model(d);Files.writeString(Path.of("engine_after_png.json"),pngIR,StandardCharsets.UTF_8);System.out.println(svgIR);
 }
}
