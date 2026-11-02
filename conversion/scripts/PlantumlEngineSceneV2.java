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
public class PlantumlEngineSceneV2 {
 static String q(Object x){if(x==null)return "null";String s=x.toString(),b="\"";for(char c:s.toCharArray()){if(c=='\\'||c=='\"')b+="\\"+c;else if(c<32)b+=String.format("\\u%04x",(int)c);else b+=c;}return b+"\"";}
 static String key(Entity e){try{byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(e.getQuark().getQualifiedName().getBytes(StandardCharsets.UTF_8));String s="own_";for(int i=0;i<16;i++)s+=String.format("%02x",b[i]);return s;}catch(Exception x){throw new RuntimeException(x);}}
 static String linkkey(Link l){try{String text=l.getUid()+"|"+l.idCommentForSvg()+"|"+(l.getLocation()==null?"":l.getLocation().getPosition());byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));String s="rel_";for(int i=0;i<16;i++)s+=String.format("%02x",b[i]);return s;}catch(Exception x){throw new RuntimeException(x);}}
 static class Owned implements IEntityImage{
  final IEntityImage d;final String key;Owned(IEntityImage d,Entity e){this.d=d;this.key=key(e);}
  public void drawU(UGraphic u){UGroup g=new UGroup();g.put(UGroupType.CLASS,"compiler-engine-owner");g.put(UGroupType.ID,key);g.put(UGroupType.DATA_ENTITY_UID,key);u.startGroup(g);try{d.drawU(u);}finally{u.closeGroup();}}
  public XDimension2D calculateDimension(StringBounder b){return d.calculateDimension(b);}public MinMax getMinMax(StringBounder b){return d.getMinMax(b);}public XRectangle2D getInnerPosition(CharSequence s,StringBounder b){return d.getInnerPosition(s,b);}public MagneticBorder getMagneticBorder(){return d.getMagneticBorder();}public HColor getBackcolor(){return d.getBackcolor();}public ShapeType getShapeType(){return d.getShapeType();}public Margins getShield(StringBounder b){return d.getShield(b);}public double getOverscanX(StringBounder b){return d.getOverscanX(b);}public boolean isHidden(){return d.isHidden();}
 }
 static void collect(Object o,IdentityHashMap<Object,Boolean> seen,List<Bibliotekon> libs,int depth)throws Exception{
  if(o==null||depth>24||seen.size()>20000||seen.put(o,true)!=null)return;
  if(o instanceof Bibliotekon){Bibliotekon b=(Bibliotekon)o;libs.add(b);for(SvekNode n:b.allNodes())collect(n.getImage(),seen,libs,depth+1);return;}
  if(o instanceof IEntityImage||o instanceof TextBlock||o instanceof DotStringFactory){for(Class<?> c=o.getClass();c!=null&&c.getName().startsWith("net.sourceforge.plantuml");c=c.getSuperclass())for(Field f:c.getDeclaredFields()){if(Modifier.isStatic(f.getModifiers())||f.getType().isPrimitive())continue;f.setAccessible(true);Object x=f.get(o);if(x instanceof Bibliotekon||x instanceof IEntityImage||x instanceof TextBlock||x instanceof DotStringFactory)collect(x,seen,libs,depth+1);}}
 }
 static List<String> instrument(CucaDiagram d)throws Exception{
  CucaDiagramFileMakerSvek m=new CucaDiagramFileMakerSvek(d);try(OutputStream out=Files.newOutputStream(Path.of("layout_ownership_unmodified.svg"))){Method dots=CucaDiagram.class.getDeclaredMethod("getDotStrings");dots.setAccessible(true);m.createFile(out,(List<String>)dots.invoke(d),new FileFormatOption(FileFormat.SVG));}
  Field bf=CucaDiagramFileMaker.class.getDeclaredField("bibliotekon");bf.setAccessible(true);List<Bibliotekon> libs=new ArrayList<>();collect(bf.get(m),new IdentityHashMap<>(),libs,0);List<String> keys=new ArrayList<>();Field image=SvekNode.class.getDeclaredField("image");image.setAccessible(true);IdentityHashMap<Entity,Owned> wrapped=new IdentityHashMap<>();for(Bibliotekon b:libs)for(SvekNode n:b.allNodes()){Entity e=b.getLeaf(n);IEntityImage original=n.getImage();Owned own=wrapped.get(e);if(own==null){own=new Owned(original,e);wrapped.put(e,own);keys.add(key(e));}image.set(n,own);e.setSvekImage(own);}Files.writeString(Path.of("ownership_instrumentation.json"),"{\"only_nonpaint_groups_added\":true,\"actual_engine_libraries\":"+libs.size()+",\"actual_engine_entities\":"+wrapped.size()+",\"same_model_image_objects_wrapped\":true}");return keys;
 }
 static String entity(Entity e){return "{\"original_uid\":"+q(e.getUid())+",\"uid\":"+q(key(e))+",\"name\":"+q(e.getName())+",\"qualified_name\":"+q(e.getQuark().getQualifiedName())+",\"display\":"+q(e.getDisplay())+",\"parent_uid\":"+q(e.getParentContainer()==null?null:key(e.getParentContainer()))+",\"is_group\":"+e.isGroup()+",\"kind\":"+q(e.isGroup()?e.getGroupType():e.getLeafType())+",\"hidden\":"+e.isHidden()+",\"removed\":"+e.isRemoved()+",\"source_line\":"+(e.getLocation()==null?"null":e.getLocation().getPosition())+"}";}
 static Diagram diagram(String source){SourceStringReader reader=new SourceStringReader(source);if(reader.getBlocks().size()!=1)throw new IllegalArgumentException("requires_single_diagram");return reader.getBlocks().get(0).getDiagram();}
 static String model(Diagram d){List<String> nodes=new ArrayList<>(),groups=new ArrayList<>(),links=new ArrayList<>();
  if(d instanceof CucaDiagram){CucaDiagram c=(CucaDiagram)d;for(Entity e:c.leafs())nodes.add(entity(e));for(Entity e:c.groups())groups.add(entity(e));for(Link l:c.getLinks())links.add("{\"original_uid\":"+q(l.getUid())+",\"svg_id\":"+q(l.idCommentForSvg())+",\"opale\":"+l.isOpale()+",\"uid\":"+q(linkkey(l))+",\"entity1_uid\":"+q(key(l.getEntity1()))+",\"entity2_uid\":"+q(key(l.getEntity2()))+",\"entity1_name\":"+q(l.getEntity1().getQuark().getQualifiedName())+",\"entity2_name\":"+q(l.getEntity2().getQuark().getQualifiedName())+",\"port1\":"+q(l.getPortName1())+",\"port2\":"+q(l.getPortName2())+",\"decor1\":"+q(l.getType().getDecor1())+",\"decor2\":"+q(l.getType().getDecor2())+",\"label\":"+q(l.getLabel())+",\"invisible\":"+l.isInvis()+",\"hidden\":"+l.isHidden()+",\"removed\":"+l.isRemoved()+",\"constraint\":"+l.isConstraint()+",\"inverted\":"+l.isInverted()+",\"source_line\":"+(l.getLocation()==null?"null":l.getLocation().getPosition())+"}");}
  return "{\"schema\":\"plantuml_engine_scene_semantic_ir_v1\",\"diagram_class\":"+q(d.getClass().getName())+",\"description\":"+q(d.getDescription())+",\"cuca_supported\":"+(d instanceof CucaDiagram)+",\"entities\":["+String.join(",",nodes)+"],\"groups\":["+String.join(",",groups)+"],\"links\":["+String.join(",",links)+"]}";
 }
 public static void main(String[] args)throws Exception{
  if(args.length==1&&args[0].equals("models")){BufferedReader br=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));String line;while((line=br.readLine())!=null){try{String src=new String(Base64.getDecoder().decode(line),StandardCharsets.UTF_8);System.out.println(model(diagram(src)));}catch(Throwable e){System.out.println("{\"error\":"+q(e.toString())+"}");}}return;}
  String source=new String(System.in.readAllBytes(),StandardCharsets.UTF_8);Diagram d=diagram(source);String before=model(d);Files.writeString(Path.of("engine_before.json"),before,StandardCharsets.UTF_8);
  if(!(d instanceof CucaDiagram)){Files.writeString(Path.of("engine_ir.json"),before,StandardCharsets.UTF_8);System.out.println(before);return;}
  try(OutputStream out=Files.newOutputStream(Path.of("source.original.svg"))){d.exportDiagram(out,0,new FileFormatOption(FileFormat.SVG));}
  try(OutputStream out=Files.newOutputStream(Path.of("source.png"))){d.exportDiagram(out,0,new FileFormatOption(FileFormat.PNG));}
  String pristineIR=model(d);Files.writeString(Path.of("engine_pristine.json"),pristineIR,StandardCharsets.UTF_8);instrument((CucaDiagram)d);
  try(OutputStream out=Files.newOutputStream(Path.of("source.svg"))){d.exportDiagram(out,0,new FileFormatOption(FileFormat.SVG));}
  String svgIR=model(d);Files.writeString(Path.of("engine_ir.json"),svgIR,StandardCharsets.UTF_8);
  String after=model(d);Files.writeString(Path.of("engine_after_png.json"),after,StandardCharsets.UTF_8);System.out.println(svgIR);
 }
}
