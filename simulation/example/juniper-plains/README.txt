JUNIPER PLAINS AREA: INVENTED EXAMPLE COMMUNITY
================================================

Everything in this folder is made up: the Juniper Plains Area, its two coordinating
councils, eight stakes and 51 wards and branches, the 297 leaders, every phone
(555-555-01xx, the range set aside for fiction), every email (@churchemcomm.sim), every
address, street, river, road, facility and map. The coordinates only place the fiction
on a map. It is safe to share, show and use in screenshots.

Independent volunteer project by Travis Hilton (W9TLH), not an official Church product.

What it is for
--------------
A public drill, a demonstration or a test without anyone's directory export. It has
the same layout as a Church directory export, so every part of the system loads it:

  Simulator        Setup -> 1. Organization pack -> this folder
                   (or: python simulation/sim_server.py --data "<this folder>")
                   Scenario: Copper Creek Dam failure (the developed example scenario)
  EOC Message      Setup -> This EOC -> Map data folder -> this folder
  Center           Setup -> Load a drill configuration -> simulation/drill-config.json
                   (build it first: python simulation/drillconfig.py simulation/drill-spec.json)
  Check it         python simulation/community.py check "<this folder>"

The valley
----------
Larkspur Valley runs 46 km north to south. The Larkspur River flows south through
Kestrel, Juniper Springs, Larkspur (the county seat) and Alder Flat. Copper Creek
leaves Copper Creek Reservoir in the eastern hills, runs west through Copper Ridge and
the south side of Larkspur, and joins the river below Center Street. Saddleback sits on
the west bench under Saddleback Ridge, where the amateur radio repeater is.

  Larkspur Coordinating Council:  Larkspur, Larkspur East, Larkspur West, Copper Ridge stakes
  Kestrel Coordinating Council:   Juniper Springs, Kestrel, Alder Flat, Saddleback stakes
  Welfare line:                   Juniper Plains Welfare and Self-Reliance Region (office in
                                  Larkspur); Bramble Junction Bishops' Storehouse, 140 km away

Special units: Larkspur Care Center Branch (care facility), Copper Ridge Retirement
Branch (retirement village), Larkspur Spanish Branch (draws members from the three
Larkspur stakes).

Maps: simulator/overlays/maps/ has a drawn street map of each stake and one of the
whole Area, placed by simulator/overlays/manifest.json like the directory's own maps.

Rebuild with: python simulation/example/build_example.py (world.json is the source).
