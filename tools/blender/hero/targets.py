"""Anthropometric targets for the hero base meshes (metres, standing A-pose, origin on the floor between the feet,
Z up, the character faces -Y, its left is +X).

Sources: adult anthropometry (stature, segment lengths and breadths, facial proportions: Farkas; a heroic 8-head male /
7.75-head female canon) checked against Epic's Manny / Quinn / MetaHuman bodies, which we measure only
(tools/reference/body_measure.py; never imported). Every number here is a target the validator checks.
"""

MALE = dict(
    sex="male",
    height=1.84, head_h=0.245,                    # vertex to chin: 7.5 heads (a realistic adult head, not a small one)
    head_breadth=0.160, head_length=0.203,        # eurion-eurion, glabella-opisthocranion
    eye_z=1.7239,                                 # .525 of the head height above the chin (adult norm)
    interpupil=0.064, eye_w=0.030,
    chin_z=1.595, neck_base_z=1.512,
    neck_w=0.140, neck_d=0.128,
    shoulder_joint=(0.182, 0.0, 1.465),           # glenohumeral centre
    biacromial=0.410, shoulder_z=1.505,           # acromion breadth / height
    chest=dict(z=1.33, w=0.355, d=0.265),         # at the nipples
    underbust=dict(z=1.25, w=0.312, d=0.235),
    waist=dict(z=1.09, w=0.266, d=0.198),
    hips=dict(z=0.95, w=0.345, d=0.240),
    crotch_z=0.880,
    hip_joint=(0.096, 0.005, 0.935),
    knee=(0.106, -0.010, 0.505),
    ankle=(0.118, 0.030, 0.085),
    thigh=dict(w=0.198, d=0.200), calf=dict(w=0.124, d=0.134),
    upper_arm=0.305, forearm=0.265, hand=0.195,   # joint to joint; hand = wrist to middle fingertip
    arm_drop=45.0, arm_fwd=8.0,                   # A-pose: degrees below horizontal, degrees forward
    upper_arm_r=0.068, forearm_r=0.050, wrist=dict(w=0.064, d=0.043),
    palm=dict(l=0.108, w=0.088, t=0.030),
    foot=dict(l=0.270, w=0.102), heel_back=0.060,
)

FEMALE = dict(
    sex="female",
    height=1.705, head_h=0.228,                   # 7.5 heads
    head_breadth=0.150, head_length=0.190,
    eye_z=1.5969,
    interpupil=0.061, eye_w=0.029,
    chin_z=1.477, neck_base_z=1.398,
    neck_w=0.116, neck_d=0.110,
    shoulder_joint=(0.160, 0.0, 1.355),
    biacromial=0.350, shoulder_z=1.388,
    chest=dict(z=1.23, w=0.300, d=0.235),         # bust
    underbust=dict(z=1.16, w=0.258, d=0.195),
    waist=dict(z=1.04, w=0.232, d=0.178),
    hips=dict(z=0.865, w=0.355, d=0.225),
    crotch_z=0.805,
    hip_joint=(0.088, 0.005, 0.860),
    knee=(0.093, -0.010, 0.465),
    ankle=(0.103, 0.028, 0.078),
    thigh=dict(w=0.172, d=0.175), calf=dict(w=0.102, d=0.112),
    upper_arm=0.285, forearm=0.240, hand=0.178,
    arm_drop=45.0, arm_fwd=8.0,
    upper_arm_r=0.047, forearm_r=0.038, wrist=dict(w=0.054, d=0.036),
    palm=dict(l=0.098, w=0.078, t=0.026),
    foot=dict(l=0.243, w=0.092), heel_back=0.055,
)

SEXES = {"male": MALE, "female": FEMALE}
