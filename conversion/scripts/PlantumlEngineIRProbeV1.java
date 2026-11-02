import java.nio.charset.StandardCharsets;
import java.util.*;
import net.sourceforge.plantuml.SourceStringReader;
import net.sourceforge.plantuml.core.Diagram;
import net.atmp.CucaDiagram;
import net.sourceforge.plantuml.abel.Entity;
import net.sourceforge.plantuml.abel.Link;
public class PlantumlEngineIRProbeV1 {
 static String q(Object x){if(x==null)return "null";String s=x.toString(),b="\"";for(char c:s.toCharArray()){if(c=='\\'||c=='\"')b+="\\"+c;else if(c<32)b+=String.format("\\u%04x",(int)c);else b+=c;}return b+"\"";}
 static String entity(Entity e){return "{\"uid\":"+q(e.getUid())+",\"name\":"+q(e.getName())+",\"qualified_name\":"+q(e.getQuark().getQualifiedName())+",\"display\":"+q(e.getDisplay())+",\"parent_uid\":"+q(e.getParentContainer()==null?null:e.getParentContainer().getUid())+",\"is_group\":"+e.isGroup()+",\"kind\":"+q(e.isGroup()?e.getGroupType():e.getLeafType())+",\"source_line\":"+(e.getLocation()==null?"null":e.getLocation().getPosition())+"}";}
 public static void main(String[] a)throws Exception{
  String source=new String(System.in.readAllBytes(),StandardCharsets.UTF_8);SourceStringReader reader=new SourceStringReader(source);
  if(reader.getBlocks().size()!=1)throw new IllegalArgumentException("requires_single_diagram");Diagram d=reader.getBlocks().get(0).getDiagram();List<String> nodes=new ArrayList<>(),groups=new ArrayList<>(),links=new ArrayList<>();
  if(d instanceof CucaDiagram){CucaDiagram c=(CucaDiagram)d;for(Entity e:c.leafs())nodes.add(entity(e));for(Entity e:c.groups())groups.add(entity(e));for(Link l:c.getLinks())links.add("{\"uid\":"+q(l.getUid())+",\"entity1_uid\":"+q(l.getEntity1().getUid())+",\"entity2_uid\":"+q(l.getEntity2().getUid())+",\"port1\":"+q(l.getPortName1())+",\"port2\":"+q(l.getPortName2())+",\"decor1\":"+q(l.getType().getDecor1())+",\"decor2\":"+q(l.getType().getDecor2())+",\"label\":"+q(l.getLabel())+",\"inverted\":"+l.isInverted()+",\"source_line\":"+(l.getLocation()==null?"null":l.getLocation().getPosition())+"}");}
  System.out.println("{\"schema\":\"plantuml_engine_semantic_ir_probe_v1\",\"diagram_class\":"+q(d.getClass().getName())+",\"description\":"+q(d.getDescription())+",\"cuca_supported\":"+(d instanceof CucaDiagram)+",\"entities\":["+String.join(",",nodes)+"],\"groups\":["+String.join(",",groups)+"],\"links\":["+String.join(",",links)+"]}");
 }
}
