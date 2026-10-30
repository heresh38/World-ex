# v96: our own names — nothing borrowed from other games' terminology
import re
def apply(s):
    R=[("GUARDIAN // ","OPERATIVE // "),("One Guardian, every option.","One operative, every option."),
       ("'Vanguard ","'Bastion "),("'Pathfinder ","'Wayfarer "),("'No class item'","'No mantle'"),
       ("['shader','Shader']","['shader','Finish']"),("<div class=sec>Shader</div>","<div class=sec>Finish</div>"),
       ("<small>POWER","<small>RATING"),("n:'Legendary'","n:'Elite'"),("n:'Exotic'","n:'Relic'"),
       ("'Exotic & legendary energy weapons'","'Relic & elite energy weapons'"),("'Sidearms & hand cannons'","'Sidearms & revolvers'"),
       ("arch:'Hand Cannon'","arch:'Heavy Revolver'"),("arch:'Linear Fusion Rifle'","arch:'Rail Lance'"),("arch:'Pulse Rifle'","arch:'Burst Rifle'"),
       ("n:'Solar'","n:'Ember'"),("n:'Arc'","n:'Volt'"),("n:'Void'","n:'Umbra'"),("n:'Stasis'","n:'Frost'"),("n:'Strand'","n:'Weave'"),("n:'Kinetic'","n:'Ballistic'"),
       ("'Sundered','Halo'","'Sundered','Hollow'"),("['cls','Class Item']","['cls','Mantle']"),("solar hand cannon","ember revolver"),("class item","mantle"),("DIRECTOR // DESTINATIONS","ATLAS // DESTINATIONS"),("Cloth over a ghost-lit mask.","Cloth over a lamp-lit mask."),("Light gathers along the forearm.","Starlight gathers along the forearm."),
       ("['weapons','Weapons'","['weapons','Handling'"),("['health','Health'","['health','Vitality'"),("['mobility','Mobility'","['mobility','Agility'"),("['recovery','Recovery'","['recovery','Regen'"),("['grenade','Grenade'","['grenade','Ordnance'"),("['melee','Melee'","['melee','Strike'"),
      ]
    for a,b in R: s=s.replace(a,b)
    s=re.sub(r"frame:'([^']*?) Frame'",lambda m:"frame:'"+m.group(1).replace('Arc ','Volt ')+" Chassis'",s)
    # element words inside player-facing sentences of the energy-weapon catalogue
    a=s.find('/* ===== v87:');b=s.find('/* ===== v88',a)
    if a>0 and b>a:
        blk=s[a:b]
        def fix(m):
            t=m.group(0)
            if ' ' not in t or 'main(' in t or 'gl_' in t or '{' in t: return t
            for x,y in [('Solar','Ember'),('solar','ember'),('Stasis','Frost'),('stasis','frost'),('Strand','Weave'),('strand','weave'),('Kinetic','Ballistic'),('kinetic','ballistic')]:
                t=re.sub(r'\b'+x+r'\b',y,t)
            t=re.sub(r'\bVoid\b','Umbra',t);t=re.sub(r'\bvoid(?=[- ]lit|\b)(?! main)','umbra',t)
            t=re.sub(r'\bArc\b','Volt',t);t=re.sub(r'\barc\b','volt',t)
            return t
        blk=re.sub(r"'(?:[^'\\\n]|\\.)*'",fix,blk)
        s=s[:a]+blk+s[b:]
    # comments / wording
    for a2,b2 in [('Destiny-style','hero-shooter style'),('Destiny-like','stylised'),('Guardian armor','operative armor'),('Guardian look','operative look'),('Destiny','our')]:
        s=s.replace(a2,b2)
    return s
