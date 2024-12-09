import bpy
import bpy.utils.previews
import sys
import os
import pathlib
addon_keymaps = []

try:
    if bpy.context.space_data != None and bpy.context.space_data.type == "TEXT_EDITOR":
        # get the path to the SAVED TO DISK script when running from blender
        print("bpy.context.space_data script_path")
        script_path = bpy.context.space_data.text.filepath
except:
    print("__file__ script_path")
    # __file__ is built-in Python variable that represents the path to the script
    script_path = __file__

print(f"script_path -> {script_path}")

script_dir = pathlib.Path(script_path).resolve().parent
print(f"[pathlib] script_dir -> {script_dir}")

moduleLocation = str(script_dir / "modules")
print(f"path_to_file -> {moduleLocation}")

if moduleLocation not in sys.path:
    sys.path.insert(0, moduleLocation)


# Now import using the modules prefix
import photoshop.api as ps

bl_info = {
    "name": "Femmy Select (UV to Photoshop Selection)",
    "author": "Hyperiya (hyperiya.vcz@outlook.com), Discord: Hyperiya",
    "version": (1),
    "blender": (2, 80, 0),
    "location": "UV Editor > UV",
    "description": "Transfer UV selection to Photoshop",
    "category": "UV",
}

print('test')
def getActiveImage(context):
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                if area.spaces.active and area.spaces.active.image:
                    return area.spaces.active.image
        return None
    
def are_uvs_connected(uv1, uv2, threshold=0.0001):
    """Check if two UV points are connected (within threshold)"""
    return (uv1 - uv2).length < threshold

class UV_PT_to_photoshop(bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'FemSelect'  # This puts it in the UV tab of the sidebar
    bl_label = "UV Tools"
    
    def draw(self, context):
        layout = self.layout
        
        # Create a row for the operator button
        row = layout.row()
        row.operator(UVToPhotoshopSelection.bl_idname, text="Send UV Selection to PS")
        
        row = layout.row()
        row.operator(ExportUVLayoutOperator.bl_idname, text="Export UV Layout (Creates new file in PS, copy paste it)")
        
        
        # Add some spacing
        layout.separator()
        
        # Create a row for the image and contact info
        contact_row = layout.row()
        
        # Left column for image
        col1 = contact_row.column()
        col1.scale_y = 0.7
        col1.template_icon(icon_value=self.get_preview_icon(), scale=5)
        
        # Right column for text
        col2 = contact_row.column()
        col2.scale_y = 1.5
        col2.label(text="Discord: Hyperiya")
        col2.label(text="Email: hyperiya.vcz@outlook.com")
        
    def get_preview_icon(self):
        pcoll = preview_collections["main"]
        return pcoll["my_icon"].icon_id
    
class ExportUVLayoutOperator(bpy.types.Operator):
    bl_idname = "uv.export_layout_to_photoshop"
    bl_label = "Export UV Layout"
    bl_description = "Export UV Layout with fill opacity 0 and all UVs visible"
    
    opacity = bpy.props.FloatProperty(
        name="Opacity",
        description="UV Layout opacity",
        default=0.0,
        min=0.0,
        max=1.0,
    )
    
    def execute(self, context):
        try:
            # Get active object
            obj = context.active_object
            if not obj or obj.type != 'MESH':
                self.report({'ERROR'}, "No mesh object selected")
                return {'CANCELLED'}
            
            # Create temporary file path
            temp_dir = bpy.app.tempdir
            file_path = os.path.join(temp_dir, "temp_uv_layout.png")
            
            # Thingy
            active_image = getActiveImage(context)
        
            if active_image:
                texture_width = active_image.size[0]
                texture_height = active_image.size[1]
            
            # Export UV layout
            bpy.ops.uv.export_layout(
                filepath=file_path,
                check_existing=False,
                export_all=True,
                modified=False,
                mode='PNG',
                size=(texture_width, texture_height),  # You can adjust the size as needed
                opacity=0,
            )
            
            # Open in Photoshop
            try:
                app = ps.Application()
                
                app.load(file_path)
                
                # Optional: Delete the temporary file
                os.remove(file_path)
                
            except Exception as e:
                self.report({'ERROR'}, f"Failed to open in Photoshop: {str(e)}")
                return {'CANCELLED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error exporting UV layout: {str(e)}")
            return {'CANCELLED'}
        
        self.report({'INFO'}, "UV Layout exported and opened in Photoshop")
        return {'FINISHED'}



preview_collections = {}

class UVToPhotoshopSelection(bpy.types.Operator):
    print('insideUVTPS')
    bl_idname = "uv.to_photoshop_selection"
    bl_label = "Send UV Selection to Photoshop"
    
    def execute(self, context):
        if context.tool_settings.mesh_select_mode[2] == False:  # [vert, edge, face]
            if not context.tool_settings.use_uv_select_sync:
                self.report({'WARNING'}, "Please enable 'UV Sync Selection' and switch to Face Select mode in the UV Editor/3D Viewport")
                return {'CANCELLED'}
                
        if context.tool_settings.mesh_select_mode[2] == False:  # [vert, edge, face]
            self.report({'WARNING'}, "Please switch to Face Select mode in the 3D Viewport/UV Editor")
            return {'CANCELLED'}
            
        # Check if UV sync is enabled
        if not context.tool_settings.use_uv_select_sync:
            self.report({'WARNING'}, "Please enable 'UV Sync Selection' in the UV Editor")
            return {'CANCELLED'}

        
        
        obj = bpy.context.active_object
        mesh = obj.data
        active_image = getActiveImage(context)
        
        if active_image:
            texture_width = active_image.size[0]
            texture_height = active_image.size[1]
        else:
            texture_width = texture_height = 1024

        try:
            import bmesh
            bm = bmesh.from_edit_mesh(mesh)
            bm.faces.ensure_lookup_table()
            
            uv_layer = bm.loops.layers.uv.verify()
            
            # Dictionary to store UV islands
            islands = {}
            island_id = 0
            processed_faces = set()

            def get_boundary_loops(start_face, processed):
                """Get boundary loops in order"""
                boundary_edges = []
                faces_to_process = [start_face]
                
                # First find all faces and boundary edges
                while faces_to_process:
                    current_face = faces_to_process.pop()
                    if current_face in processed:
                        continue
                        
                    processed.add(current_face)
                    
                    # Check each edge
                    for edge in current_face.edges:
                        linked_faces = [f for f in edge.link_faces if f.select]
                        # If edge has only one selected face, it's a boundary
                        if len(linked_faces) == 1:
                            boundary_edges.append(edge)
                        else:
                            # Add unprocessed linked faces
                            for f in linked_faces:
                                if f not in processed:
                                    faces_to_process.append(f)
                
                # Sort boundary edges into connected loops
                boundary_loops = []
                while boundary_edges:
                    current_loop = []
                    current_edge = boundary_edges.pop(0)
                    current_vert = current_edge.verts[0]
                    
                    while True:
                        # Add the current edge's UV coordinates
                        for loop in current_edge.link_loops:
                            if loop.face in processed:
                                uv = loop[uv_layer].uv
                                ps_x = uv.x * texture_width
                                ps_y = (1 - uv.y) * texture_height
                                current_loop.append([ps_x, ps_y])
                                break
                        
                        # Find the next connected edge
                        next_edge = None
                        for edge in current_vert.link_edges:
                            if edge in boundary_edges:
                                next_edge = edge
                                boundary_edges.remove(edge)
                                current_vert = edge.other_vert(current_vert)
                                break
                        
                        if not next_edge:
                            break
                        
                        current_edge = next_edge
                    
                    if current_loop:
                        boundary_loops.append(current_loop)
                
                return boundary_loops

            # Find all UV islands
            for face in bm.faces:
                if face.select and face not in processed_faces:
                    boundary_loops = get_boundary_loops(face, processed_faces)
                    for loop in boundary_loops:
                        if len(loop) > 2:  # Only add valid loops
                            islands[island_id] = loop
                            island_id += 1

            # Debug info
            for island_id, points in islands.items():
                print(f"Island {island_id} has {len(points)} points:")
                for i, point in enumerate(points):
                    print(f"  Point {i}: ({point[0]:.1f}, {point[1]:.1f})")

            # Create selections in Photoshop
            try:
                app = ps.Application()
                doc = app.activeDocument
                
                # Clear any existing selection
                doc.selection.deselect()
                
                # Create selection for each island
                first_selection = True
                for island_points in islands.values():
                    if len(island_points) > 2:
                        # Close the polygon by adding first point at the end
                        if island_points[0] != island_points[-1]:
                            island_points.append(island_points[0])
                        
                        try:
                            if first_selection:
                                # First selection creates new
                                doc.selection.select(island_points, ps.SelectionType.ReplaceSelection)
                                first_selection = False
                            else:
                                # Subsequent selections add to existing
                                doc.selection.select(island_points, ps.SelectionType.ExtendSelection)
                        except Exception as e:
                            print(f"Error creating selection: {str(e)}")
                            print(f"Points that caused error: {island_points}")
                            continue

            except Exception as e:
                self.report({'ERROR'}, f"Failed to communicate with Photoshop: {str(e)}")
                return {'CANCELLED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error processing UV data: {str(e)}")
            return {'CANCELLED'}
        finally:
            bm.free()

        if not islands:
            self.report({'WARNING'}, "No UV points selected")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Transferred {len(islands)} UV island selections to Photoshop")
        return {'FINISHED'}





    
def menu_func(self, context):
    self.layout.operator(UVToPhotoshopSelection.bl_idname)

def register():
    # Add the shortcut
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    pcoll = bpy.utils.previews.new()
    icon_path =  os.path.join(script_dir, "resources/icon.png")
    pcoll.load("my_icon", icon_path, 'IMAGE')

    preview_collections["main"] = pcoll
    
    if kc:
        # Image Editor keymap
        km = kc.keymaps.new(name='Image Generic', space_type='IMAGE_EDITOR')
        kmi = km.keymap_items.new(
            UVToPhotoshopSelection.bl_idname,
            type='P',
            value='PRESS',
            ctrl=True,
            shift=True
        )
        addon_keymaps.append((km, kmi))
        
    bpy.utils.register_class(UVToPhotoshopSelection)
    bpy.utils.register_class(UV_PT_to_photoshop)
    bpy.utils.register_class(ExportUVLayoutOperator)
    bpy.types.VIEW3D_MT_uv_map.append(menu_func)
    
def unregister():
    # Remove the shortcut
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    
    bpy.utils.unregister_class(UVToPhotoshopSelection)
    bpy.utils.unregister_class(UV_PT_to_photoshop)
    bpy.utils.unregister_class(ExportUVLayoutOperator)
    
    bpy.types.VIEW3D_MT_uv_map.remove(menu_func)



if __name__ == "__main__":
    register()
