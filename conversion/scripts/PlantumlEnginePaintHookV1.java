import java.util.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import net.sourceforge.plantuml.abel.Entity;
import net.sourceforge.plantuml.svek.*;
import net.sourceforge.plantuml.klimt.*;
import net.sourceforge.plantuml.klimt.drawing.UGraphic;
public class PlantumlEnginePaintHookV1 {
 public static boolean enabled=false;
 private static final Map<String,Integer> owners=new TreeMap<>();
 public static String key(Entity e){try{byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(e.getQuark().getQualifiedName().getBytes(StandardCharsets.UTF_8));String s="own_";for(int i=0;i<16;i++)s+=String.format("%02x",b[i]);return s;}catch(Exception x){throw new RuntimeException(x);}}
 public static void draw(IEntityImage image,UGraphic u,SvekNode node){if(!enabled){image.drawU(u);return;}try{Field f=SvekNode.class.getDeclaredField("leaf");f.setAccessible(true);Entity e=(Entity)f.get(node);String k=key(e);owners.put(k,owners.getOrDefault(k,0)+1);UGroup g=new UGroup();g.put(UGroupType.CLASS,"compiler-engine-owner");g.put(UGroupType.ID,k);u.startGroup(g);try{image.drawU(u);}finally{u.closeGroup();}}catch(ReflectiveOperationException e){throw new RuntimeException(e);}}
 public static String report(){StringBuilder b=new StringBuilder("{\"only_nonpaint_groups_added\":true,\"actual_layout_model_or_image_cache_mutations\":0,\"actual_engine_entities\":"+owners.size()+",\"draw_site_patches\":"+PlantumlEngineDrawAgentV1.patches+",\"draw_site\":\""+PlantumlEngineDrawAgentV1.method+"\",\"actual_source_owner_draw_calls\":{");boolean first=true;for(Map.Entry<String,Integer> e:owners.entrySet()){if(!first)b.append(",");first=false;b.append("\"").append(e.getKey()).append("\":").append(e.getValue());}return b.append("}}").toString();}
}
