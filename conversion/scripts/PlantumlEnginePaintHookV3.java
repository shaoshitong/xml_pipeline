import java.util.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import net.sourceforge.plantuml.abel.Entity;
import net.sourceforge.plantuml.abel.Link;
import net.sourceforge.plantuml.svek.*;
import net.sourceforge.plantuml.klimt.*;
import net.sourceforge.plantuml.klimt.drawing.UGraphic;
public class PlantumlEnginePaintHookV3 {
 public static boolean enabled=false;
 public static Object expectedDiagram=null;
 public static UGraphic wrapPNG(UGraphic png,net.sourceforge.plantuml.klimt.geom.XDimension2D dim,double scale,Object builder){if(!enabled)return png;try{Field f=builder.getClass().getDeclaredField("diagram");f.setAccessible(true);if(f.get(builder)!=expectedDiagram)return png;return new PlantumlEngineDualGraphicV1(png,dim,scale);}catch(ReflectiveOperationException e){throw new RuntimeException(e);}}

 private static final Map<String,Integer> owners=new TreeMap<>();
 public static String key(Entity e){try{byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(e.getQuark().getQualifiedName().getBytes(StandardCharsets.UTF_8));String s="own_";for(int i=0;i<16;i++)s+=String.format("%02x",b[i]);return s;}catch(Exception x){throw new RuntimeException(x);}}
 public static void draw(IEntityImage image,UGraphic u,SvekNode node){if(!enabled){image.drawU(u);return;}try{Field f=SvekNode.class.getDeclaredField("leaf");f.setAccessible(true);Entity e=(Entity)f.get(node);String k=key(e);owners.put(k,owners.getOrDefault(k,0)+1);UGroup g=new UGroup();g.put(UGroupType.CLASS,"compiler-engine-owner");g.put(UGroupType.ID,k);u.startGroup(g);try{image.drawU(u);}finally{u.closeGroup();}}catch(ReflectiveOperationException e){throw new RuntimeException(e);}}
 private static final Map<String,String> links=new TreeMap<>();
 static String q(Object v){if(v==null)return "null";String x=v.toString(),b="\"";for(char c:x.toCharArray()){if(c=='\\'||c=='\"')b+="\\"+c;else if(c<32)b+=String.format("\\u%04x",(int)c);else b+=c;}return b+"\"";}
 static String linkkey(Link l){try{String text=l.getUid()+"|"+l.idCommentForSvg()+"|"+(l.getLocation()==null?"":l.getLocation().getPosition());byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));String s="rel_";for(int i=0;i<16;i++)s+=String.format("%02x",b[i]);return s;}catch(Exception x){throw new RuntimeException(x);}}
 public static void beginEdge(SvekEdge edge,UGraphic u){if(!enabled)return;try{Link l=null;for(Class<?> c=edge.getClass();c!=null;c=c.getSuperclass())for(Field f:c.getDeclaredFields())if(f.getType()==Link.class){f.setAccessible(true);l=(Link)f.get(edge);}if(l==null)throw new IllegalStateException("missing_actual_SvekEdge_Link_object");String k=linkkey(l);links.put(k,"{\"entity1_uid\":"+q(key(l.getEntity1()))+",\"entity2_uid\":"+q(key(l.getEntity2()))+",\"actual_start_uid_prefix\":"+q(edge.getStartUidPrefix())+",\"actual_end_uid_prefix\":"+q(edge.getEndUidPrefix())+",\"original_link_uid\":"+q(l.getUid())+",\"original_svg_comment_id\":"+q(l.idCommentForSvg())+",\"original_source_line\":"+(l.getLocation()==null?"null":l.getLocation().getPosition())+"}");UGroup g=new UGroup();g.put(UGroupType.CLASS,"compiler-engine-link");g.put(UGroupType.ID,k);u.startGroup(g);}catch(ReflectiveOperationException e){throw new RuntimeException(e);}}
 public static void endEdge(UGraphic u){if(enabled)u.closeGroup();}
 public static String linkReport(){StringBuilder b=new StringBuilder("{");boolean first=true;for(Map.Entry<String,String> e:links.entrySet()){if(!first)b.append(",");first=false;b.append(q(e.getKey())).append(":").append(e.getValue());}return b.append("}").toString();}
 public static String report(){StringBuilder b=new StringBuilder("{\"only_nonpaint_groups_added\":true,\"actual_layout_model_or_image_cache_mutations\":0,\"actual_engine_entities\":"+owners.size()+",\"draw_site_patches\":"+PlantumlEngineDrawAgentV3.patches+",\"draw_site\":\""+PlantumlEngineDrawAgentV3.method+"\",\"actual_source_owner_draw_calls\":{");boolean first=true;for(Map.Entry<String,Integer> e:owners.entrySet()){if(!first)b.append(",");first=false;b.append("\"").append(e.getKey()).append("\":").append(e.getValue());}return b.append("},\"actual_source_link_objects\":").append(linkReport()).append("}").toString();}
}
