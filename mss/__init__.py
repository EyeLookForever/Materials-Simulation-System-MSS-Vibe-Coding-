"""
Materials Simulation System (MSS)
v0.0000000000001 - Experimental Prototype

A simulation engine covering physics, chemistry, biology, and engineering.
Rather than hard-coding fixed "recipes" (e.g. iron + copper = wire), the
system models the REAL PHYSICAL PROPERTIES of matter and derives behavior
from them: state of matter, chemical reactions, cell growth, and even what
technologies can be built from an arbitrary combination of materials.

Package layout:
    core          - shared math tools and the simulation clock (Universe)
    chemistry     - periodic table, known compounds, arbitrary substances
    physics       - heat/mechanics/electricity and nuclear physics
    biology       - genomes, cells, environments, evolving populations
    engineering   - invention discovery and buildable devices
    programming   - a tiny player-defined programming language and VM
    cli           - the interactive command-line demo
"""
