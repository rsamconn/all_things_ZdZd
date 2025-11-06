#--------------------------------------------------------------------
# Get configuration from JO name
#--------------------------------------------------------------------
from MadGraphControl.MadGraphUtilsHelpers import get_physics_short

# Example JO name: mc.aMCPy8_ZZd_4l_Signal_mS125_mZd5.py -> tokens = ['mS125', 'mZd5']
tokens = get_physics_short().replace('.py', '').split('_')[-2:] # Extract mass parameters as list

print(tokens)

mh = float([t for t in tokens if t.startswith('mS')][0].removeprefix('mS')) #  Higgs mass [GeV] (also used for dark Higgs mass)
mzd = float([t for t in tokens if t.startswith('mZd')][0].removeprefix('mZd')) # Zd mass [GeV]

print(mh)
print(mzd)

print(f'Generation parameters:')
print(f'  {mh=}')
print(f'  {mzd=}')

evgenConfig.description=f"MadGraph Hidden Abelian Higgs Model (HAHM): gg -> H -> ZZd -> 4l (l=e,mu) , with mZd={mzd}GeV"
evgenConfig.keywords+=['exotic','BSMHiggs']
evgenConfig.contact = ['matthew.peter.connell@cern.ch']
evgenConfig.generators = ['MadGraph', 'Pythia8', 'EvtGen']

# JO for Release 21 based on the template: https://gitlab.cern.ch/atlas-physics/pmg/mcjoboptions/blob/master/950xxx/950116/mc.MGPy8EG_A14NNPDF23_ttbar_Incl_valid.py
# Additional doc included in: https://twiki.cern.ch/twiki/bin/view/AtlasProtected/MadGraph5aMCatNLOForAtlas#LO_Pythia8_Showering

import MadGraphControl.MadGraph_NNPDF30NLOnf4_Base_Fragment
from MadGraphControl.MadGraphUtils import *

nevents = runArgs.maxEvents*1.1 if runArgs.maxEvents>0 else 1.1*evgenConfig.nEventsPerJob

process = """
import model HAHM_variableMW_v3_UFO_GFfix
define l+ = e+ mu+
define l- = e- mu-
define j = u c d s b u~ c~ d~ s~ b~
generate g g > h HIG=1 HIW=0 QED=0 QCD=0, (h > Z Zp, Z > l+ l-, Zp > l+ l-)
output -f"""

process_dir = new_process(process)

#Fetch default LO run_card.dat and set parameters
settings = {'lhe_version':'3.0',
            'nevents':int(nevents)}

settings_param_card = { "HIDDEN": { 'epsilon': '1e-4', #kinetic mixing parameter
                                 'kap': '1e-10', #higgs mixing parameter
                                 'mzdinput': mzd, #Zd mass
                                 'mhsinput': '200.0' }, #dark higgs mass
                     "HIGGS": { 'mhinput': mh }, #higgs mass
                     "DECAY": { 'wzp':'Auto', 'wh':'Auto', 'wt':'Auto' } #auto-calculate decay widths and BR of Zp, H, t
                  }

modify_param_card(process_dir=process_dir,params=settings_param_card)

modify_run_card(process_dir=process_dir,runArgs=runArgs,settings=settings)
            
generate(process_dir=process_dir,runArgs=runArgs)

arrange_output(process_dir=process_dir,runArgs=runArgs,lhe_version=3,saveProcDir=False)

#### Shower
include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
include("Pythia8_i/Pythia8_MadGraph.py")
#include("Pythia8_i/Pythia8_aMcAtNlo.py")
