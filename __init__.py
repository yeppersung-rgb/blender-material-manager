bl_info = {
    "name": "Material Manager",
    "author": "Yepper_sung",
    "version": (2, 1, 0), # 更新了版本号
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > MatManager",
    "description": "Ultimate material manager with smart PBR setup, global replace, and deep purge.",
    "category": "Material",
}

import bpy
import os
import re
from bpy_extras.io_utils import ImportHelper

# ==========================================
# 1. 操作符：选择使用了指定材质的模型
# ==========================================
class MATERIAL_OT_select_assigned(bpy.types.Operator):
    bl_idname = "material.select_assigned"
    bl_label = "Select Assigned"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_mat = context.scene.my_mat_manager_target
        if not target_mat:
            self.report({'WARNING'}, "Please select a Target Material first!")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        count = 0
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                for slot in obj.material_slots:
                    if slot.material == target_mat:
                        obj.select_set(True)
                        count += 1
                        break
                        
        self.report({'INFO'}, f"Selected {count} object(s)")
        return {'FINISHED'}


# ==========================================
# [新增] 操作符：一键清空选中模型的所有材质
# ==========================================
class MATERIAL_OT_remove_all_materials(bpy.types.Operator):
    bl_idname = "material.remove_all_materials"
    bl_label = "Remove All Materials"
    bl_description = "Clear all material slots from selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objs = context.selected_objects
        if not selected_objs:
            self.report({'WARNING'}, "Please select at least one object!")
            return {'CANCELLED'}
        
        count = 0
        for obj in selected_objs:
            # 确保对象具有材质数据属性 (排除空物体、摄像机等)
            if hasattr(obj.data, "materials"):
                obj.data.materials.clear()
                count += 1
                
        self.report({'INFO'}, f"Cleared materials from {count} object(s).")
        return {'FINISHED'}


# ==========================================
# [新增] 操作符：将目标材质赋予选中模型
# ==========================================
class MATERIAL_OT_apply_target_material(bpy.types.Operator):
    bl_idname = "material.apply_target_material"
    bl_label = "Apply Target Material"
    bl_description = "Apply the Target Material to all selected objects (replaces existing)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target_mat = context.scene.my_mat_manager_target
        if not target_mat:
            self.report({'WARNING'}, "Please select a Target Material first!")
            return {'CANCELLED'}
            
        selected_objs = context.selected_objects
        if not selected_objs:
            self.report({'WARNING'}, "Please select at least one object!")
            return {'CANCELLED'}
            
        count = 0
        for obj in selected_objs:
            if hasattr(obj.data, "materials"):
                # 先清空原有材质，然后追加新材质
                obj.data.materials.clear()
                obj.data.materials.append(target_mat)
                count += 1
                
        self.report({'INFO'}, f"Applied '{target_mat.name}' to {count} object(s).")
        return {'FINISHED'}


# ==========================================
# 2. 操作符：全局材质替换
# ==========================================
class MATERIAL_OT_replace_global(bpy.types.Operator):
    bl_idname = "material.replace_global"
    bl_label = "Replace Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        old_mat = context.scene.my_mat_manager_target
        new_mat = context.scene.my_mat_replace_target
        
        if not old_mat or not new_mat:
            self.report({'WARNING'}, "Please specify both Target and Replace materials!")
            return {'CANCELLED'}
            
        count = 0
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                for slot in obj.material_slots:
                    if slot.material == old_mat:
                        slot.material = new_mat
                        count += 1
                        
        self.report({'INFO'}, f"Replaced material on {count} slot(s).")
        return {'FINISHED'}


# ==========================================
# 3. 操作符：智能 PBR 自动连线 (终极后缀匹配版)
# ==========================================
class MATERIAL_OT_auto_pbr_setup(bpy.types.Operator, ImportHelper):
    bl_idname = "material.auto_pbr_setup"
    bl_label = "Auto PBR Setup"
    bl_options = {'REGISTER', 'UNDO'}

    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    
    filter_glob: bpy.props.StringProperty(
        default="*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.exr",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        if not self.files:
            return {'CANCELLED'}

        mat = context.scene.my_mat_manager_target
        if not mat:
            self.report({'WARNING'}, "Please select a Target Material first!")
            return {'CANCELLED'}
            
        # --- 智能文件搜集 (排除 preview) ---
        files_to_load = []
        valid_exts = ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr')
        
        if len(self.files) == 1:
            selected_file = self.files[0].name
            base_name = os.path.splitext(selected_file)[0]
            prefix = ""
            for separator in ['_', '-']:
                if separator in base_name:
                    prefix = base_name.rsplit(separator, 1)[0] + separator
                    break
            for f in os.listdir(self.directory):
                if not f.lower().endswith(valid_exts) or 'preview' in f.lower():
                    continue
                if prefix and not f.startswith(prefix):
                    continue
                files_to_load.append(f)
        else:
            for f in self.files:
                if 'preview' not in f.name.lower():
                    files_to_load.append(f.name)

        # --- 构建节点树 ---
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)
        
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (300, 0)
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        
        mapping = nodes.new(type='ShaderNodeMapping')
        mapping.location = (-1000, 0)
        tex_coord = nodes.new(type='ShaderNodeTexCoord')
        tex_coord.location = (-1200, 0)
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

        # --- 核心辅助函数：安全连线 ---
        def safe_link(tex_out_socket, target_input_names):
            for name in target_input_names:
                if name in bsdf.inputs:
                    links.new(tex_out_socket, bsdf.inputs[name])
                    return True
            return False

        # --- 贴图识别字典 ---
        map_keywords = {
            'COLOR': ['color', 'albedo', 'diffuse', 'basecolor', 'base'],
            'METALLIC': ['metal', 'metallic', 'mtl', 'metalness'],
            'ROUGHNESS': ['rough', 'roughness', 'rgh'],
            'NORMAL': ['normal', 'nor', 'nrm'],
            'BUMP': ['bump', 'bmp'],
            'DISPLACEMENT': ['disp', 'displacement', 'height'],
            'SHEEN': ['sheen'],
            'ANISOTROPY': ['aniso', 'anisotropy'],
            'TINT': ['edgetint', 'tint'],
            'EMISSION_STRENGTH': ['emissionstrength', 'emitstrength', 'glowstrength'],
            'EMISSION_COLOR': ['emit', 'emission', 'emissive', 'glow'],
            'OPACITY': ['alpha', 'opacity', 'mask'],
            'TRANSMISSION': ['transmission', 'glass', 'refraction'],
            'SSS_SCALE': ['scatteringdistancescale'],
            'SSS_COLOR': ['scatteringcolor'],
            'SSS_WEIGHT': ['sss', 'subsurface', 'scatter'],
            'CLEARCOAT': ['coat', 'clearcoat'],
            'CLEARCOAT_ROUGHNESS': ['coatroughness', 'clearcoatroughness'],
            'IOR': ['ior'],
            'SPECULAR': ['spec', 'specular'],
        }

        y_offset = 400 
        has_displacement = False
        
        for file_name_str in files_to_load:
            file_name = file_name_str.lower()
            file_path = os.path.join(self.directory, file_name_str)
            
            # --- 核心算法：按结束位置与长度双重校验 ---
            clean_name = re.sub(r'[^a-z0-9]', '', file_name)
            best_match = None
            highest_end_idx = -1
            longest_kw_len = 0
            
            for map_type, kw_list in map_keywords.items():
                for kw in kw_list:
                    idx = clean_name.rfind(kw)
                    if idx > -1:
                        end_idx = idx + len(kw)
                        if end_idx > highest_end_idx or (end_idx == highest_end_idx and len(kw) > longest_kw_len):
                            highest_end_idx = end_idx
                            longest_kw_len = len(kw)
                            best_match = map_type

            # 创建图像节点
            img = bpy.data.images.load(file_path)
            tex_node = nodes.new(type='ShaderNodeTexImage')
            tex_node.image = img
            tex_node.location = (-600, y_offset)
            links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])
            
            # 自动处理色彩空间
            srgb_maps = ['COLOR', 'EMISSION_COLOR', 'SSS_COLOR', 'TINT']
            if best_match not in srgb_maps:
                tex_node.image.colorspace_settings.name = 'Non-Color'

            # 智能安全连线 
            if best_match == 'COLOR':
                safe_link(tex_node.outputs['Color'], ['Base Color'])
            elif best_match == 'METALLIC':
                safe_link(tex_node.outputs['Color'], ['Metallic'])
            elif best_match == 'ROUGHNESS':
                safe_link(tex_node.outputs['Color'], ['Roughness'])
            elif best_match == 'ANISOTROPY':
                safe_link(tex_node.outputs['Color'], ['Anisotropic', 'Anisotropy'])
            elif best_match == 'TINT':
                safe_link(tex_node.outputs['Color'], ['Specular Tint', 'Tint'])
            elif best_match == 'SHEEN':
                safe_link(tex_node.outputs['Color'], ['Sheen Weight', 'Sheen'])
            elif best_match == 'NORMAL':
                normal_map = nodes.new(type='ShaderNodeNormalMap')
                normal_map.location = (-300, y_offset - 50)
                links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                safe_link(normal_map.outputs['Normal'], ['Normal'])
            elif best_match == 'BUMP':
                bump_map = nodes.new(type='ShaderNodeBump')
                bump_map.location = (-300, y_offset - 50)
                links.new(tex_node.outputs['Color'], bump_map.inputs['Height'])
                safe_link(bump_map.outputs['Normal'], ['Normal'])
            elif best_match == 'DISPLACEMENT':
                has_displacement = True
                disp_node = nodes.new(type='ShaderNodeDisplacement')
                disp_node.location = (0, -200)
                links.new(tex_node.outputs['Color'], disp_node.inputs['Height'])
                links.new(disp_node.outputs['Displacement'], output.inputs['Displacement'])
            elif best_match == 'OPACITY':
                safe_link(tex_node.outputs['Color'], ['Alpha'])
                # 单独安全处理透明混合模式
                if hasattr(mat, 'blend_method'):
                    mat.blend_method = 'HASHED'
                # 单独安全处理阴影混合模式（兼容 Blender 4.2+ Eevee Next）
                if hasattr(mat, 'shadow_method'):
                    mat.shadow_method = 'HASHED'
            elif best_match == 'TRANSMISSION':
                safe_link(tex_node.outputs['Color'], ['Transmission Weight', 'Transmission'])
            elif best_match == 'EMISSION_STRENGTH':
                safe_link(tex_node.outputs['Color'], ['Emission Strength'])
            elif best_match == 'EMISSION_COLOR':
                safe_link(tex_node.outputs['Color'], ['Emission Color', 'Emission'])
            elif best_match == 'SSS_SCALE':
                safe_link(tex_node.outputs['Color'], ['Subsurface Scale'])
            elif best_match == 'SSS_COLOR':
                safe_link(tex_node.outputs['Color'], ['Subsurface Radius', 'Subsurface Color'])
            elif best_match == 'SSS_WEIGHT':
                safe_link(tex_node.outputs['Color'], ['Subsurface Weight', 'Subsurface'])
            elif best_match == 'CLEARCOAT':
                safe_link(tex_node.outputs['Color'], ['Coat Weight', 'Clearcoat'])
            elif best_match == 'CLEARCOAT_ROUGHNESS':
                safe_link(tex_node.outputs['Color'], ['Coat Roughness', 'Clearcoat Roughness'])
            elif best_match == 'IOR':
                safe_link(tex_node.outputs['Color'], ['IOR'])
            elif best_match == 'SPECULAR':
                safe_link(tex_node.outputs['Color'], ['Specular IOR Level', 'Specular'])
                
            y_offset -= 250 

        # --- 安全处理置换模式 (终极暴力兼容版) ---
        if has_displacement:
            # 1. 尝试 Blender 4.2+ 的全局置换设置
            try:
                mat.displacement_method = 'BOTH'
            except Exception:
                pass
                
            try:
                mat.displacement_method = 'DISPLACEMENT_BUMP'
            except Exception:
                pass
                
            # 2. 尝试老版本 Blender 的 Cycles 专属设置
            try:
                mat.cycles.displacement_method = 'BOTH'
            except Exception:
                pass
                
            try:
                mat.cycles.displacement_method = 'DISPLACEMENT_BUMP'
            except Exception:
                pass
                
        self.report({'INFO'}, f"Successfully linked {len(files_to_load)} maps to '{mat.name}'!")
        return {'FINISHED'}


# ==========================================
# 4. 操作符：精准清理未使用材质 (白名单机制)
# ==========================================
class MATERIAL_OT_purge_materials(bpy.types.Operator):
    bl_idname = "material.purge_unused_mats"
    bl_label = "Purge Unused Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        used_mats = set()
        for obj in bpy.data.objects:
            for slot in obj.material_slots:
                if slot.material:
                    used_mats.add(slot.material.name)
        count = 0
        for mat in list(bpy.data.materials):
            if mat.name not in used_mats and not mat.use_fake_user:
                bpy.data.materials.remove(mat, do_unlink=True)
                count += 1
        self.report({'INFO'}, f"Purged {count} unused material(s)")
        return {'FINISHED'}


# ==========================================
# 5. 操作符：深度清理未使用贴图 (白名单机制)
# ==========================================
class MATERIAL_OT_purge_images(bpy.types.Operator):
    bl_idname = "material.purge_unused_images"
    bl_label = "Purge Unused Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        used_images = set()
        def scan_tree_for_images(tree):
            if not tree: return
            for node in tree.nodes:
                if hasattr(node, 'image') and node.image:
                    used_images.add(node.image.name)
                if node.type == 'GROUP' and node.node_tree:
                    scan_tree_for_images(node.node_tree)
        
        for mat in bpy.data.materials:
            scan_tree_for_images(mat.node_tree)
        for world in bpy.data.worlds:
            scan_tree_for_images(world.node_tree)
        for brush in bpy.data.brushes:
            if getattr(brush, 'texture', None) and getattr(brush.texture, 'image', None):
                used_images.add(brush.texture.image.name)
                
        count = 0
        leftover = []
        for img in list(bpy.data.images):
            if img.name in ["Render Result", "Viewer Node"]:
                continue
            if img.name not in used_images and not img.use_fake_user:
                try:
                    bpy.data.images.remove(img, do_unlink=True)
                    count += 1
                except Exception as e:
                    leftover.append(f"{img.name}")
                    
        if leftover:
            self.report({'WARNING'}, f"Purged {count}, but {len(leftover)} failed.")
        else:
            self.report({'INFO'}, f"Perfect! Purged {count} unused image(s).")
        return {'FINISHED'}


# ==========================================
# 6. 面板 UI：界面布局
# ==========================================
class MATERIAL_PT_manager_panel(bpy.types.Panel):
    bl_label = "Material Manager"
    bl_idname = "MATERIAL_PT_manager_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MatManager'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 模块 1：选择与分配 (更新了布局)
        box1 = layout.box()
        box1.label(text="1. Select & Assign", icon='MATERIAL')
        box1.prop(scene, "my_mat_manager_target", text="Target")
        
        row = box1.row(align=True)
        row.operator(MATERIAL_OT_apply_target_material.bl_idname, text="Apply to Selected", icon='ADD')
        row.operator(MATERIAL_OT_select_assigned.bl_idname, text="Select Assigned", icon='RESTRICT_SELECT_OFF')
        
        box1.operator(MATERIAL_OT_remove_all_materials.bl_idname, text="Remove All Materials", icon='X')

        layout.separator()

        # 模块 2：全局替换
        box2 = layout.box()
        box2.label(text="2. Global Replace", icon='NODE_MATERIAL')
        box2.prop(scene, "my_mat_replace_target", text="Replace")
        box2.operator(MATERIAL_OT_replace_global.bl_idname, text="Replace Material", icon='FILE_REFRESH')

        layout.separator()
        
        # 模块 3：工作流工具
        box3 = layout.box()
        box3.label(text="3. Workflow Tools", icon='TEXTURE')
        box3.operator(MATERIAL_OT_auto_pbr_setup.bl_idname, text="Auto PBR Setup", icon='IMPORT')

        layout.separator()

        # 模块 4：深度清理
        box4 = layout.box()
        box4.label(text="4. Deep Cleanup", icon='TRASH')
        box4.operator(MATERIAL_OT_purge_materials.bl_idname, text="Purge Unused Material", icon='BRUSH_DATA')
        box4.operator(MATERIAL_OT_purge_images.bl_idname, text="Purge Unused Image", icon='IMAGE_DATA')

        layout.separator()
        layout.label(text="Author: Yepper_sung", icon='USER')


# ==========================================
# 7. 注册与注销机制
# ==========================================
classes = (
    MATERIAL_OT_select_assigned,
    MATERIAL_OT_remove_all_materials,    # 新增类注册
    MATERIAL_OT_apply_target_material,   # 新增类注册
    MATERIAL_OT_replace_global,
    MATERIAL_OT_auto_pbr_setup,
    MATERIAL_OT_purge_materials,
    MATERIAL_OT_purge_images,
    MATERIAL_PT_manager_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.my_mat_manager_target = bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="Target Material"
    )
    bpy.types.Scene.my_mat_replace_target = bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="Replace With"
    )

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.my_mat_manager_target
    del bpy.types.Scene.my_mat_replace_target

if __name__ == "__main__":
    register()