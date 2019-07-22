bl_info = {
    "name": "Bevel Curve Tools",
    "author": "Yusuf Umar",
    "version": (0, 1, 1),
    "blender": (2, 80, 0),
    "location": "View 3D > Tool Shelf > Curve",
    "description": "Tool to help add and maintain beveled curve easier",
    "wiki_url": "https://github.com/ucupumar/bevel-curve-tools",
    "category": "Add Curve",
}

import bpy, math
from mathutils import Vector, Quaternion
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty

HIDDEN_COLLECTION_NAME = '_HIDDEN_BEVEL_OBJECTS'

def is_28():
    return bpy.app.version_string.startswith('2.8')

def set_active_object(obj):
    if is_28():
        bpy.context.view_layer.objects.active = obj
    else: bpy.context.scene.objects.active = obj

def get_object_select(obj):
    if is_28():
        try: return obj.select_get()
        except: return False
    else: return obj.select

def set_object_select(obj, val):
    if is_28():
        obj.select_set(val)
    else: obj.select = val

def mul(A, B):
    if is_28():
        return A @ B
    else: return A * B

def hide_object(obj, val):
    if is_28():
        obj.hide_viewport = val
    else: obj.hide = val

def link_object(scene, obj):
    if is_28():
        scene.collection.objects.link(obj)
    else: scene.objects.link(obj)

def get_scene_objects():
    if is_28():
        return bpy.context.view_layer.objects
    else: return bpy.context.scene.objects

def get_set_collection(collection_name, parent_collection=None):
    if collection_name in bpy.data.collections: # Does the collection already exist?
        return bpy.data.collections[collection_name]
    else:
        new_collection = bpy.data.collections.new(collection_name)
        if parent_collection: parent_collection.children.link(new_collection) # Add the new collection under a parent
        return new_collection

def radius_falloff(points, power = 1.0, tip = 'ONE'):
    total_points = len(points)
    for i, point in enumerate(points):
        dist = i/(total_points-1)
        if tip == 'ONE':
            radius_weight = max(1.0 - pow(dist, power), 0.01)
        elif tip == 'DUAL':
            if dist >= 0.5:
                dist = (dist - 0.5) * 2.0
                radius_weight = max(1.0 - pow(dist, power), 0.01)
            else:
                dist = dist * 2.0
                radius_weight = max(pow(dist, 1/power), 0.01)
        elif tip == 'NO':
            radius_weight = 1.0
        #print(dist, radius_weight)
        point.radius = radius_weight

def get_spline_points(spline):
    # Points for griffindor
    if spline.type in {'POLY', 'NURBS'}:
        points = spline.points
    else:
        points = spline.bezier_points

    return points

def get_point_position(curve_obj, index=0, spline_index=0):
    curve_mat = curve_obj.matrix_world
    curve = curve_obj.data
    points = get_spline_points(curve.splines[spline_index])
    return mul(curve_mat, points[index].co.xyz)

def bool_union(context):
    obj = context.active_object
    sel_objs = [o for o in context.selected_objects if o != obj]
    for o in sel_objs:

        set_active_object(obj)

        # Add boolean modifier
        md = obj.modifiers.new('booleanunion', 'BOOLEAN')
        md.operation = 'UNION'
        md.object = o       

        # Apply the modifier
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier="booleanunion")

        # Delete current object
        bpy.ops.object.select_all(action='DESELECT')
        set_active_object(o)
        set_object_select(o, True)
        bpy.ops.object.delete()

    set_active_object(obj)

def convert_curve_to_mesh(context, mode='NOMERGE'):

    # Listing selected curve objects
    objs = get_scene_objects()

    selected_objs = [o for o in objs if 
            get_object_select(o) and 
            o.type == 'CURVE' and 
            o.data.bevel_object]

    if mode == 'UNION' or mode == 'SEPARATE':

        for o in selected_objs:

            splines = o.data.splines
            spline_len = len(splines)

            # If spline is more than one, do separation
            if spline_len > 1:

                set_active_object(o)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.curve.select_all(action='DESELECT')

                # Do reversed loop to separate
                for i in reversed(range(1, spline_len)):
                    if splines[i].type == 'NURBS':
                        for p in splines[i].points:
                            p.select = True
                    else:
                        for bp in splines[i].bezier_points:
                            bp.select_control_point = True
                    bpy.ops.curve.separate()

                bpy.ops.object.editmode_toggle()

        # Do listing selected curve objects again
        selected_objs = [o for o in objs if 
                get_object_select(o) and 
                o.type == 'CURVE' and 
                o.data.bevel_object]

    # Listing bevel objects of selected objects
    sel_bev_objs = [o.data.bevel_object for o in selected_objs]

    # Listing bevel objects of not selected objects
    not_sel_bev_objs = [o.data.bevel_object for o in objs if 
            not get_object_select(o) and 
            o.type == 'CURVE' and 
            o.data.bevel_object]

    # Listing bevel objecs to delete if not used anywhere
    bev_objs_to_del = list()
    for bev_ob in sel_bev_objs:
        if bev_ob not in not_sel_bev_objs and bev_ob not in bev_objs_to_del:
            bev_objs_to_del.append(bev_ob)

    # convert curve to mesh
    bpy.ops.object.convert(target='MESH')
    
    bpy.ops.object.select_all(action='DESELECT')

    # Unhide collection
    if is_28():
        col = context.view_layer.layer_collection.children.get(HIDDEN_COLLECTION_NAME)
        if col: col.exclude = False

    for o in bev_objs_to_del:
        # bring to active layer
        if not is_28():
            for i in range(20):
                o.layers[i] = context.scene.layers[i]
        # show and select them
        hide_object(o, False)
        set_object_select(o, True)
    # Delete them objects
    bpy.ops.object.delete()

    # Remove vertex duplication
    for o in selected_objs:
        #print(o)
        set_active_object(o)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.editmode_toggle()
        set_object_select(o, True)

    if mode == 'MERGE':
        bpy.ops.object.join()
    elif mode == 'UNION' and len(selected_objs) > 1:
        bool_union(context)

    # Smooth shade object
    bpy.ops.object.shade_smooth()

    # Select object
    set_object_select(context.active_object, True)

    # Hide back collection
    if is_28():
        col = context.view_layer.layer_collection.children.get(HIDDEN_COLLECTION_NAME)
        if col: col.exclude = True

def check_bevel_used_by_other_objects(curve_obj):

    bevel_used = False

    for o in get_scene_objects():
        if (o.type == 'CURVE' and
            o != curve_obj and
            o.data.bevel_object == curve_obj.data.bevel_object):
            bevel_used = True

    return bevel_used

def get_point_rotation(context, scene, curve_obj, index=0, spline_index=0):

    # Get curve attributes
    curve_mat = curve_obj.matrix_world
    curve = curve_obj.data
    points = get_spline_points(curve.splines[spline_index])

    # new temp object to detect local x-axis and y-axis of first handle
    # Temp Bevel Object for temp curve
    temp_bevel_curve = bpy.data.curves.new('__temp_bevel', 'CURVE')
    temp_spline = temp_bevel_curve.splines.new('POLY')
    temp_spline.points.add(2)
    temp_spline.points[0].co = Vector((1.0, 0.0, 0.0, 1.0))
    temp_spline.points[1].co = Vector((0.0, 1.0, 0.0, 1.0))
    temp_bevel_obj = bpy.data.objects.new('__temp_bevel', temp_bevel_curve)
    link_object(scene, temp_bevel_obj)
    # Temp Curve
    curve_copy = curve_obj.data.copy()
    curve_copy.use_fill_caps = False
    curve_copy.bevel_object = temp_bevel_obj
    temp_obj = bpy.data.objects.new('__temp', curve_copy)
    link_object(scene, temp_obj)
    temp_obj.location = curve_obj.location
    temp_obj.rotation_mode = curve_obj.rotation_mode
    temp_obj.rotation_quaternion = curve_obj.rotation_quaternion
    temp_obj.rotation_euler = curve_obj.rotation_euler

    # Convert temp curve to mesh
    bpy.ops.object.select_all(action='DESELECT') # deselect all first
    set_active_object(temp_obj)
    set_object_select(temp_obj, True)
    bpy.ops.object.convert(target='MESH')

    offset = 0
    micro_offset = 0

    #cyclic check
    for i, spline in enumerate(curve.splines):
        if i > spline_index:
            break
        #ps = get_spline_points(spline)
        if i > 0:
            ps_count = len(get_spline_points(curve.splines[i-1]))
            offset += ps_count-1
        if spline.use_cyclic_u:
            offset += 1
        elif i > 0:
            micro_offset += 1

    #offset += spline_index * curve.resolution_u
    #print(offset)

    # get x-axis and y-axis of the first handle
    handle_x = temp_obj.data.vertices[curve.resolution_u * (index + offset) * 3 + micro_offset * 3].co
    handle_y = temp_obj.data.vertices[curve.resolution_u * (index + offset) * 3 + 1 + micro_offset * 3].co

    target_x = handle_x - points[index].co.xyz
    target_y = handle_y - points[index].co.xyz
    target_x.normalize()
    target_y.normalize()

    # delete temp objects
    set_object_select(temp_bevel_obj, True)
    bpy.ops.object.delete()
    
    # Match bevel x-axis to handle x-axis
    bevel_x = Vector((1.0, 0.0, 0.0))
    target_x = mul(curve_mat.to_3x3(), target_x)
    rot_1 = bevel_x.rotation_difference(target_x)

    # Match bevel y-axis to handle y-axis
    bevel_y = mul(rot_1.to_matrix(), Vector((0.0, 1.0, 0.0)))
    target_y = mul(curve_mat.to_3x3(), target_y)
    rot_2 = bevel_y.rotation_difference(target_y)

    # Select curve object again
    set_active_object(curve_obj)
    set_object_select(curve_obj, True)

    return mul(rot_2, rot_1)

def get_proper_index_bevel_placement(curve_obj):
    """ Returns (spline index, point index) """
    idx = (0, 0)
    found = False

    for i, spline in enumerate(curve_obj.data.splines):
        points = get_spline_points(spline)
        # Prioritising radius of 1.0
        for j, point in enumerate(points):
            if spline.type == 'NURBS':
                if j > 0:
                    idx = (i, j)
                    found = True
                    break
            elif point.radius == 1.0:
                idx = (i, j)
                found = True
                break
        if found:
            break

    # If still not found do another loop
    if not found:
        for i, spline in enumerate(curve_obj.data.splines):
            points = get_spline_points(spline)
            for j, point in enumerate(points):
                if spline.type == 'NURBS':
                    if j > 0:
                        idx = (i, j)
                        break
                elif point.radius <= 1.0 and point.radius >= 0.3:
                    temp_ps = get_spline_points(curve_obj.data.splines[idx[0]])
                    old_radius = temp_ps[idx[1]].radius
                    # get the biggest radius under 1.0
                    if point.radius > old_radius or old_radius > 1.0:
                        idx = (i, j)
    
    #print(idx)
    return idx

def main_draw(self, context):
    obj = context.active_object
    col = self.layout.column()
    if context.mode == 'OBJECT':
        col.label(text="New:")
        col.operator("curve.y_new_beveled_curve", icon='CURVE_DATA')
        col.label(text="Edit:")
        c = col.column(align=True)
        c.operator("curve.y_add_bevel_to_curve", icon='MESH_DATA')
        c.operator("curve.y_edit_bevel_curve", icon='EDITMODE_HLT')
        if is_28():
            c.operator("curve.y_hide_bevel_objects", icon='HIDE_ON')
        else: c.operator("curve.y_hide_bevel_objects", icon='VISIBLE_IPO_OFF')

        #if obj and obj.type =='CURVE':
        col.label(text="Convert:")
        c = col.column(align=True)
        c.operator("curve.y_convert_beveled_curve_to_meshes", icon='OBJECT_DATA')
        c.operator("curve.y_convert_beveled_curve_to_separated_meshes", icon='OBJECT_DATA')
        c.operator("curve.y_convert_beveled_curve_to_merged_mesh", icon='OBJECT_DATA')
        c.operator("curve.y_convert_beveled_curve_to_union_mesh", icon='OBJECT_DATA')

        if obj and obj.type == 'CURVE':
            col.label(text="Properties:")
            col.prop(obj.data, "resolution_u")

    elif context.mode =='EDIT_CURVE':
        col.alert = True
        col.operator("curve.y_finish_edit_bevel")
        col.alert = False

class YBevelCurveToolPanel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    #bl_context = "objectmode"
    bl_label = "Bevel Curve Tools"
    bl_category = "Curve"
    
    def draw(self, context):
        main_draw(self, context)

class YBevelCurveToolUIPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = 'Bevel Curve Tools'
    bl_region_type = 'UI'
    bl_category = 'Curve'

    def draw(self, context):
        main_draw(self, context)

class YFinishEditBevel(bpy.types.Operator):
    bl_idname = "curve.y_finish_edit_bevel"
    bl_label = "Finish Edit Bevel"
    bl_description = "Finish edit bevel and back to object mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_CURVE' and not context.object.data.bevel_object

    def execute(self, context):
        bpy.ops.object.editmode_toggle()
        
        bevel_obj = context.active_object
        
        # Hide bevel object
        hide_object(bevel_obj, True)

        if is_28():
            # Hide collection
            col = context.view_layer.layer_collection.children.get(HIDDEN_COLLECTION_NAME)
            if col: col.exclude = True
        else:
            # Bring back bevel object to layer 19
            bevel_obj.layers[19] = True
            for i in range(19):
                bevel_obj.layers[i] = False

        # Select curve object back
        for obj in get_scene_objects():
            if obj.type == 'CURVE' and obj.data.bevel_object and obj.data.bevel_object == bevel_obj:
                set_object_select(obj, True)
                set_active_object(obj)

        return {'FINISHED'}

class YNewBeveledCurve(bpy.types.Operator):
    bl_idname = "curve.y_new_beveled_curve"
    bl_label = "New Beveled Curve"
    bl_description = "Create new beveled curve"
    bl_options = {'REGISTER', 'UNDO'}

    curve_type = EnumProperty(
            name = 'Type',
            description="Curve Type", 
            items = (
                ('BEZIER', "Bezier", ""),
                ('NURBS', "NURBS", ""),
                ),
            default='BEZIER',
            )

    shape = EnumProperty(
            name = "Shape",
            description="Use predefined shape of bevel", 
            items=(
                ('SQUARE', "Square", ""),
                ('HALFCIRCLE', "Half-Circle", ""),
                ('CIRCLE', "Circle", ""),
                ('TRIANGLE', "Triangle", ""),
                ), 
            default='TRIANGLE',
            )

    subsurf = BoolProperty(
            name="Use SubSurf Modifier",
            default=False,
            )

    radius = FloatProperty(
            name="Size (Curve)",
            description="Size of the curve",
            min=0.1, max=10.0,
            default=1.0,
            step=0.3,
            precision=3
            )

    scale_x = FloatProperty(
            name="Scale X (Bevel Object)",
            description="X scaling",
            min=0.1, max=10.0,
            default=1.0,
            step=0.3,
            precision=3
            )

    scale_y = FloatProperty(
            name="Scale Y (Bevel Object)",
            description="Y scaling",
            min=0.1, max=10.0,
            default=1.0,
            step=0.3,
            precision=3
            )

    rotation = FloatProperty(
            name="Rotate",
            description="Tilt rotation",
            unit='ROTATION',
            min=0.0, max=math.pi*2.0,
            default=0.0,
            )

    falloff = EnumProperty(
            name = "Radius Falloff",
            description="Falloff of beveled curve", 
            items=(
                ('DUALTIP', "Dual Tip", ""),
                ('ONETIP', "One Tip", ""),
                ('NOTIP', "No Tip", ""),
                ), 
            default='ONETIP',
            )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):

        if self.curve_type == 'BEZIER':
            bpy.ops.curve.primitive_bezier_curve_add(radius = self.radius)
        else: bpy.ops.curve.primitive_nurbs_curve_add(radius = self.radius)

        bpy.ops.curve.y_add_bevel_to_curve(
            scale_x = self.scale_x,
            scale_y = self.scale_y,
            rotation = self.rotation,
            shape = self.shape,
            falloff = self.falloff,
            subsurf = self.subsurf)
        return {'FINISHED'}

class YConvertCurveToSeparatedMesh(bpy.types.Operator):
    bl_idname = "curve.y_convert_beveled_curve_to_separated_meshes"
    bl_label = "To Separated Meshes"
    bl_description = "Convert beveled curve to sperated meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # check if curve is selected
        obj = bpy.context.active_object
        return context.mode == 'OBJECT' and obj and obj.type == 'CURVE' and obj.data.bevel_object

    def execute(self, context):
        convert_curve_to_mesh(context, 'SEPARATE')
        return {'FINISHED'}

class YConvertCurveToMergedMesh(bpy.types.Operator):
    bl_idname = "curve.y_convert_beveled_curve_to_merged_mesh"
    bl_label = "To Merged Mesh"
    bl_description = "Convert beveled curve to one merged mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # check if curve is selected
        obj = bpy.context.active_object
        return context.mode == 'OBJECT' and obj and obj.type == 'CURVE' and obj.data.bevel_object

    def execute(self, context):
        convert_curve_to_mesh(context, 'MERGE')
        return {'FINISHED'}

class YConvertCurveToUnionMesh(bpy.types.Operator):
    bl_idname = "curve.y_convert_beveled_curve_to_union_mesh"
    bl_label = "To Union Mesh"
    bl_description = "Convert beveled curve to one union mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # check if curve is selected
        obj = bpy.context.active_object
        return context.mode == 'OBJECT' and obj and obj.type == 'CURVE' and obj.data.bevel_object

    def execute(self, context):
        convert_curve_to_mesh(context, 'UNION')
        return {'FINISHED'}

class YConvertCurveToMesh(bpy.types.Operator):
    bl_idname = "curve.y_convert_beveled_curve_to_meshes"
    bl_label = "To Mesh(es)"
    bl_description = "Convert beveled curve to meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # check if curve is selected
        obj = bpy.context.active_object
        return context.mode == 'OBJECT' and obj and obj.type == 'CURVE' and obj.data.bevel_object

    def execute(self, context):
        convert_curve_to_mesh(context, 'NOMERGE')
        return {'FINISHED'}

class YHideBevelObjects(bpy.types.Operator):
    bl_idname = "curve.y_hide_bevel_objects"
    bl_label = "Hide Bevel Objects"
    bl_description = "Hide all bevel objects in the scene"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):

        bevel_objs = list()

        if is_28():
            # Hide collection
            col = context.view_layer.layer_collection.children.get(HIDDEN_COLLECTION_NAME)
            if col: col.exclude = True

        for obj in get_scene_objects():
            if obj.type == 'CURVE' and obj.data.bevel_object and obj.data.bevel_object not in bevel_objs:
                bevel_objs.append(obj.data.bevel_object)
            if '_bevel' in obj.name and  obj not in bevel_objs:
                bevel_objs.append(obj)
        
        if not is_28():
            # Change object's layer to only layer 19
            for obj in bevel_objs:
                obj.layers[19] = True
                for i in range(19):
                    obj.layers[i] = False

        # Hide objects
        for obj in bevel_objs:
            hide_object(obj, True)
        
        return {'FINISHED'}

class YEditBevelCurve(bpy.types.Operator):
    bl_idname = "curve.y_edit_bevel_curve"
    bl_label = "Edit Bevel"
    bl_description = "Edit bevel shape of curve"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Check if curve is selected
        obj = context.active_object
        return context.mode == 'OBJECT' and obj and obj.type == 'CURVE' and obj.data.bevel_object

    def execute(self, context):

        scn = context.scene
        obj = context.active_object
        curve = obj.data
        bevel_obj = curve.bevel_object

        # Hide all bevel objects around first
        bpy.ops.curve.y_hide_bevel_objects()

        # Duplicate bevel object if it's used by other object
        bevel_used = check_bevel_used_by_other_objects(obj)
        if bevel_used:
            bevel_obj = bpy.data.objects.new(obj.name + '_bevel', bevel_obj.data.copy())

            if is_28():
                col = get_set_collection(HIDDEN_COLLECTION_NAME, scn.collection)
                col.objects.link(bevel_obj)
            else: link_object(scn, bevel_obj)

            curve.bevel_object = bevel_obj

        idx = get_proper_index_bevel_placement(obj)
        bevel_rotation = get_point_rotation(context, scn, obj, index=idx[1], spline_index=idx[0])
        bevel_position = get_point_position(obj, index=idx[1], spline_index=idx[0])

        # Set object rotation and location
        bevel_obj.rotation_mode = 'QUATERNION'
        bevel_obj.rotation_quaternion = bevel_rotation
        bevel_obj.location = bevel_position

        if is_28():
            # Unhide collection
            col = context.view_layer.layer_collection.children.get(HIDDEN_COLLECTION_NAME)
            if col: col.exclude = False
        else:
            # Show bevel object on active layer
            for i in range(20):
                bevel_obj.layers[i] = scn.layers[i]

        # Show object if hidden
        hide_object(bevel_obj, False)

        bpy.ops.object.select_all(action='DESELECT')
        set_active_object(bevel_obj)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

class YAddBevelToCurve(bpy.types.Operator):
    bl_idname = "curve.y_add_bevel_to_curve"
    bl_label = "Add/Override Bevel"
    bl_description = "Add or override bevel to curve object"
    bl_options = {'REGISTER', 'UNDO'}

    shape = EnumProperty(
            name = "Shape",
            description="Use predefined shape of bevel", 
            items=(
                ('SQUARE', "Square", ""),
                ('HALFCIRCLE', "Half-Circle", ""),
                ('CIRCLE', "Circle", ""),
                ('TRIANGLE', "Triangle", ""),
                ), 
            default='TRIANGLE',
            )

    subsurf = BoolProperty(
            name="Use SubSurf Modifier",
            default=False,
            )

    scale_x = FloatProperty(
            name="Scale X (Bevel Object)",
            description="X scaling",
            min=0.1, max=10.0,
            default=1.0,
            step=0.3,
            precision=3
            )

    scale_y = FloatProperty(
            name="Scale Y (Bevel Object)",
            description="Y scaling",
            min=0.1, max=10.0,
            default=1.0,
            step=0.3,
            precision=3
            )

    rotation = FloatProperty(
            name="Rotate",
            description="Tilt rotation",
            unit='ROTATION',
            min=0.0, max=math.pi*2.0,
            default=0.0,
            )

    falloff = EnumProperty(
            name = "Radius Falloff",
            description="Falloff of beveled curve", 
            items=(
                ('DUALTIP', "Dual Tip", ""),
                ('ONETIP', "One Tip", ""),
                ('NOTIP', "No Tip", ""),
                ), 
            default='ONETIP',
            )

    #falloff_power = FloatProperty(
    #        name="Falloff Power",
    #        description="Power of the falloff",
    #        min=1.0, max=10.0,
    #        default=1.0,
    #        step=1.0,
    #        precision=2
    #        )

    #resolution = IntProperty(
    #        name="Resolution U",
    #        description="Resolution between points",
    #        min=1, max=64,
    #        default=12,
    #        step=1,
    #        )

    @classmethod
    def poll(cls, context):
        if not context.mode == 'OBJECT':
            return False
        # check if curve is selected
        obj = context.active_object
        if obj and obj.type == 'CURVE':
            # Bevel object cannot use bevel too
            bevel_match = any(o for o in get_scene_objects() if o.type == 'CURVE' and o.data.bevel_object == obj)
            if bevel_match:
                return False
            else:
                return True
        return False

    def execute(self, context):

        curve_obj = context.active_object
        scn = context.scene
        curve = curve_obj.data

        # Set resolution
        #curve.resolution_u = self.resolution
        #curve.render_resolution_u = self.resolution

        # First spline
        splines = curve_obj.data.splines
        points = get_spline_points(splines[0])

        if len(points) < 2:
            self.report({'ERROR'}, "Just one point wouldn't do it")
            return {'CANCELLED'}  
        
        if len(points) == 2 and self.falloff == 'DUALTIP':
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.curve.select_all(action='SELECT')
            bpy.ops.curve.subdivide() #number_cuts=3)
            bpy.ops.object.editmode_toggle()
            # spline data changes, so it must be retreived again
            splines = curve_obj.data.splines
            points = get_spline_points(splines[0])

        # Spline setup
        for spline in splines:
            # Cardinal is better
            spline.tilt_interpolation = 'CARDINAL'
            spline.radius_interpolation = 'CARDINAL'

            ps = get_spline_points(spline)

            # Set tilt rotation
            for p in ps:
                p.tilt = self.rotation

            #if spline.type == 'NURBS' or self.falloff == 'NOTIP':
            if self.falloff == 'NOTIP':
                radius_falloff(ps, tip='NO')

            elif self.falloff == 'ONETIP':
                radius_falloff(ps, tip='ONE')

            elif self.falloff == 'DUALTIP':
                radius_falloff(ps, tip='DUAL')

        # Delete old bevel object if it's already there
        if curve.bevel_object:

            # Check if other object using this bevel object
            bevel_used = check_bevel_used_by_other_objects(curve_obj)
            
            if not bevel_used:
                if is_28():
                    col = context.view_layer.layer_collection.children.get(HIDDEN_COLLECTION_NAME)
                    if col: col.exclude = False

                # Delete old bevel object
                bevel_obj = curve.bevel_object
                hide_object(bevel_obj, False)
                bpy.ops.object.select_all(action='DESELECT')
                set_object_select(bevel_obj, True)
                set_active_object(bevel_obj)
                bpy.ops.object.delete()

                if is_28():
                    col = context.view_layer.layer_collection.children.get(HIDDEN_COLLECTION_NAME)
                    if col: col.exclude = True

                # Reselect curve_obj
                set_object_select(curve_obj, True)
                set_active_object(curve_obj)

        # Point coords
        triangle_coords = [
                (-0.055, 0.0), (-0.06, 0.01),
                (-0.005, 0.1), (0.005, 0.1),
                (0.06, 0.01), (0.055, 0.0)]

        halfcircle_coords = [
                (-0.06, 0.0), (-0.06, 0.01),
                (-0.045, 0.07), (0.0, 0.1), (0.045, 0.07),
                (0.06, 0.01), (0.06, 0.0)]

        circle_coords = [
                (-0.036, 0.014), (-0.05, 0.05),
                (-0.036, 0.086), (0.0, 0.1), (0.036, 0.086),
                (0.05, 0.05), (0.036, 0.014)]

        square_coords = [
                (0.0, 0.04), (0.01, 0.05), 
                (0.09, 0.05), (0.1, 0.04), 
                (0.1, 0.0),
                (0.1, -0.04), (0.09, -0.05), 
                (0.01, -0.05), (0.0, -0.04)]

        if self.shape == 'TRIANGLE':
            coords = triangle_coords
        elif self.shape == 'HALFCIRCLE':
            coords = halfcircle_coords
        elif self.shape == 'CIRCLE':
            coords = circle_coords
        elif self.shape == 'SQUARE':
            coords = square_coords

        # New object and curve data
        bevel_curve = bpy.data.curves.new(curve_obj.name + '_bevel', 'CURVE')
        bevel_curve.dimensions = '3D'
        bevel_curve.resolution_u = 2
        if not is_28():
            bevel_curve.show_normal_face = False

        # Add new spline and set it's points to bevel curve
        new_spline = bevel_curve.splines.new('POLY')
        new_spline.use_cyclic_u = True
        new_spline.points.add(len(coords))
        for i, co in enumerate(coords):
            new_spline.points[i].co = Vector((co[0], co[1], 0.0, 1.0))

        # Create new bevel object
        bevel_obj = bpy.data.objects.new(curve_obj.name + '_bevel', bevel_curve)
        if not is_28():
            link_object(scn, bevel_obj)

        # Add bevel to curve
        curve.bevel_object = bevel_obj
        curve.use_fill_caps = True
        
        # Scale the points
        #for spline in bevel_curve.splines:
        ps = get_spline_points(bevel_curve.splines[0])
        sum_x = 0.0
        sum_y = 0.0
        for p in ps:
            sum_x += p.co.x
            sum_y += p.co.y

        offset_x = sum_x / len(ps)
        offset_y = sum_y / len(ps)

        for p in ps:
            # Offset to center the origins 
            p.co.x -= offset_x
            p.co.y -= offset_y

            # then scale
            p.co.x *= self.scale_x
            p.co.y *= self.scale_y
            
        if self.falloff == 'DUALTIP':
            midindex = int((len(points)-1)/2)
            bevel_rotation = get_point_rotation(context, scn, curve_obj, index=midindex)
            bevel_position = get_point_position(curve_obj, index=midindex)
        else: 
            bevel_rotation = get_point_rotation(context, scn, curve_obj)
            bevel_position = get_point_position(curve_obj)

        # Set object rotation and location
        bevel_obj.rotation_mode = 'QUATERNION'
        bevel_obj.rotation_quaternion = bevel_rotation
        bevel_obj.location = bevel_position

        # Send bevel object to layer 20
        if is_28():
            col = get_set_collection(HIDDEN_COLLECTION_NAME, scn.collection)
            col.objects.link(bevel_obj)
            context.view_layer.layer_collection.children[HIDDEN_COLLECTION_NAME].exclude = True
        else:
            bevel_obj.layers[19] = True
            for i in range(19):
                bevel_obj.layers[i] = False

        # Hide bevel by default
        hide_object(bevel_obj, True)

        # Add/remove subsurf
        subsurf_found = False
        modifiers = curve_obj.modifiers
        for m in modifiers:
            if m.type == 'SUBSURF':
                subsurf_found = True
        
        if self.subsurf == False:
            if subsurf_found == True:
                for m in modifiers:
                    if m.type == 'SUBSURF':
                        bpy.ops.object.modifier_remove(modifier=m.name)

        if self.subsurf == True:
            if subsurf_found == False:
                bpy.ops.object.modifier_add(type='SUBSURF')

        return {'FINISHED'}

def register():

    if is_28():
        bpy.utils.register_class(YBevelCurveToolUIPanel)
    else: bpy.utils.register_class(YBevelCurveToolPanel)
    bpy.utils.register_class(YFinishEditBevel)
    bpy.utils.register_class(YNewBeveledCurve)
    bpy.utils.register_class(YConvertCurveToSeparatedMesh)
    bpy.utils.register_class(YConvertCurveToMergedMesh)
    bpy.utils.register_class(YConvertCurveToUnionMesh)
    bpy.utils.register_class(YConvertCurveToMesh)
    bpy.utils.register_class(YHideBevelObjects)
    bpy.utils.register_class(YEditBevelCurve)
    bpy.utils.register_class(YAddBevelToCurve)

def unregister():
    if is_28():
        bpy.utils.unregister_class(YBevelCurveToolUIPanel)
    else: bpy.utils.unregister_class(YBevelCurveToolPanel)
    bpy.utils.unregister_class(YFinishEditBevel)
    bpy.utils.unregister_class(YNewBeveledCurve)
    bpy.utils.unregister_class(YConvertCurveToSeparatedMesh)
    bpy.utils.unregister_class(YConvertCurveToMergedMesh)
    bpy.utils.unregister_class(YConvertCurveToUnionMesh)
    bpy.utils.unregister_class(YConvertCurveToMesh)
    bpy.utils.unregister_class(YHideBevelObjects)
    bpy.utils.unregister_class(YEditBevelCurve)
    bpy.utils.unregister_class(YAddBevelToCurve)

if __name__ == "__main__":
    register()
