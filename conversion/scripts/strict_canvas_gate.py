"""A declared page may replace a legacy tight render only with actual padded-pixel proof."""
def require_declared_page(render,width,height):
 assert render['selected_image']=='declared_first_page','Native content requires full tight canvas'
 assert render['output_size']==[width,height],'Native output size differs from reference canvas'
 assert not render['content_outside_declared_canvas'],'Native content lies outside declared canvas'
 boundary=render['outside_page_pixel_audit']
 assert boundary['white_threshold']==255 and boundary['nonwhite_outside_pixels']==0,'Actual padded render contains visible pixels outside the page'
 return True
