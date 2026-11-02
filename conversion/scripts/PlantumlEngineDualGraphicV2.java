import java.io.*;
import java.nio.file.*;
import java.util.*;
import net.sourceforge.plantuml.klimt.*;
import net.sourceforge.plantuml.klimt.shape.*;
import net.sourceforge.plantuml.klimt.geom.*;
import net.sourceforge.plantuml.klimt.font.*;
import net.sourceforge.plantuml.klimt.color.*;
import net.sourceforge.plantuml.klimt.drawing.*;
import net.sourceforge.plantuml.klimt.drawing.svg.*;
import net.sourceforge.plantuml.url.Url;
public class PlantumlEngineDualGraphicV2 implements UGraphic {
 static class Shared{UGraphicSvg owned,pristine;Deque<Boolean> skip=new ArrayDeque<>();Map<String,Integer> classes=new TreeMap<>();int originalCalls=0,ownedCalls=0,pristineCalls=0;}
 final UGraphic png,owned,pristine;final Shared s;
 public PlantumlEngineDualGraphicV2(UGraphic png,XDimension2D dim,double scale,net.sourceforge.plantuml.skin.Pragma pragma){this.png=png;s=new Shared();SvgOption option=SvgOption.basic().withPragma(pragma).withLengthAdjust(LengthAdjust.SPACING).withMinDim(dim).withScale(scale).withColorMapper(png.getColorMapper()).withBackcolor(png.getDefaultBackground()).withPreserveAspectRatio("none").withSvgDimensionStyle(true);s.owned=UGraphicSvg.build(option,false,0L,png.getStringBounder());s.pristine=UGraphicSvg.build(option,false,0L,png.getStringBounder());owned=s.owned;pristine=s.pristine;}
 private PlantumlEngineDualGraphicV2(UGraphic p,UGraphic a,UGraphic b,Shared s){png=p;owned=a;pristine=b;this.s=s;}
 public StringBounder getStringBounder(){return png.getStringBounder();}public UParam getParam(){return png.getParam();}public ColorMapper getColorMapper(){return png.getColorMapper();}public HColor getDefaultBackground(){return png.getDefaultBackground();}public boolean matchesProperty(String p){return png.matchesProperty(p);}
 public <S extends UShape> void draw(S shape){png.draw(shape);s.originalCalls++;owned.draw(shape);s.ownedCalls++;pristine.draw(shape);s.pristineCalls++;String k=shape.getClass().getName();s.classes.put(k,s.classes.getOrDefault(k,0)+1);}
 public UGraphic apply(UChange c){return new PlantumlEngineDualGraphicV2(png.apply(c),owned.apply(c),pristine.apply(c),s);}
 public void startUrl(Url u){png.startUrl(u);owned.startUrl(u);pristine.startUrl(u);}public void closeUrl(){png.closeUrl();owned.closeUrl();pristine.closeUrl();}
 public void startGroup(UGroup g){png.startGroup(g);owned.startGroup(g);String cls=g.asMap().get(UGroupType.CLASS);boolean skip=cls!=null&&(cls.equals("compiler-engine-owner")||cls.equals("compiler-engine-link"));s.skip.push(skip);if(!skip)pristine.startGroup(g);}
 public void closeGroup(){png.closeGroup();owned.closeGroup();if(s.skip.isEmpty())throw new IllegalStateException("source_owner_group_stack_underflow");if(!s.skip.pop())pristine.closeGroup();}
 public void flushUg(){png.flushUg();owned.flushUg();pristine.flushUg();}
 public void writeToStream(OutputStream out,String metadata,int dpi)throws IOException{png.writeToStream(out,metadata,dpi);if(!s.skip.isEmpty())throw new IllegalStateException("source_owner_groups_not_closed");try(OutputStream o=Files.newOutputStream(Path.of("source.svg"))){s.owned.writeToStream(o,metadata,dpi);}try(OutputStream o=Files.newOutputStream(Path.of("source.original.svg"))){s.pristine.writeToStream(o,metadata,dpi);}StringBuilder b=new StringBuilder("{\"same_layout_and_paint_call_stream\":true,\"original_PNG_draw_calls\":"+s.originalCalls+",\"owned_SVG_draw_calls\":"+s.ownedCalls+",\"pristine_SVG_draw_calls\":"+s.pristineCalls+",\"original_PNG_string_bounder_used\":true,\"shape_classes\":{");boolean first=true;for(Map.Entry<String,Integer> e:s.classes.entrySet()){if(!first)b.append(",");first=false;b.append("\"").append(e.getKey()).append("\":").append(e.getValue());}Files.writeString(Path.of("same_paint_stream.json"),b.append("}}").toString());}
}
