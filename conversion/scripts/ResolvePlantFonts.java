import java.awt.Font;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import sun.font.*;
import net.sourceforge.plantuml.klimt.font.UFont;
public class ResolvePlantFonts {
 static String enc(String s){return Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8));}
 static String dec(String s){return new String(Base64.getDecoder().decode(s),StandardCharsets.UTF_8);}
 public static void main(String[] args) throws Exception {
  BufferedReader r=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));String line;
  while((line=r.readLine())!=null){String[] a=line.split("\\t",-1);String family=dec(a[0]).replace("'","\"").replaceAll("(?i)sans-serif","SansSerif").replaceAll("(?i)^monospace$","Monospaced");String text=dec(a[3]);Font f=UFont.build(family,Integer.parseInt(a[1]),Integer.parseInt(a[2])).getUnderlayingFont(text);Font2D fd=FontUtilities.getFont2D(f);Map<String,Integer> counts=new LinkedHashMap<>();for(int cp:text.codePoints().toArray()){String physical;if(fd instanceof CompositeFont){CompositeFont c=(CompositeFont)fd;int glyph=c.getMapper().charToGlyph(cp);physical=c.getSlotFont(glyph>>>24).getFamilyName(Locale.ROOT);}else physical=fd.getFamilyName(Locale.ROOT);counts.put(physical,counts.getOrDefault(physical,0)+1);}if(counts.isEmpty())counts.put(fd instanceof CompositeFont?((CompositeFont)fd).getSlotFont(0).getFamilyName(Locale.ROOT):fd.getFamilyName(Locale.ROOT),0);String selected=Collections.max(counts.entrySet(),Map.Entry.comparingByValue()).getKey();System.out.println(enc(selected)+"\t"+enc(String.join("|",counts.keySet()))+"\t"+f.canDisplayUpTo(text)+"\t"+enc(f.getFamily()));}
 }
}
