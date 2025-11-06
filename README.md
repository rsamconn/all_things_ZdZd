# all_things_ZdZd
Various useful tools for the H/S -> XX/ZX -> 4l particle physics analysis.

## Generation and derivation
Sometimes it can be useful to generate a few signal samples to test aspects of the Monte Carlo generation.

The generation treats the Higgs boson, H, and the Additional Scalar, S, equivalently (H will have a 125 GeV mass, any other mass will be S).

The relevant files are in the signal_generation folder:
- `MGPy8EG_ZdZd_4l_Signal_mSX_mZdX.py` - the Job Options (JO) file which sets the parameters of the generation for H->ZdZd->4l
- `mc.MGPy8EG_ZdZd_4l_Signal_mS125_mZd30.py` - brief control script to call the H->ZdZd->4l JO file.
- `MGPy8EG_ZZd_4l_Signal_mSX_mZdX.py` - the Job Options (JO) file which sets the parameters of the generation for H->ZdZd->4l
- `mc.MGPy8EG_ZZd_4l_Signal_mS125_mZd30.py` - brief control script to call the H->ZdZd->4l JO file.

Assuming the generation is performed on lxplus via remote login, the generation commands are:
- `mkdir gen_example; cd gen_example`
- Copy the desired JO file and control script to gen_example
- `setupATLAS`
- `asetup 23.6.40,AthGeneration`
- `Gen_tf.py --ecmEnergy=13000.0 --jobConfig=$PWD --outputEVNTFile=tmp.EVNT.root --maxEvents=1000 --randomSeed=2`
  - If the generation runs successfully the terminal output should end with 'exit code 0' and there should be a `tmp.EVNT.root` file (~30 MB for 1000 events).
  - To switch from Run 2 to Run 3 generation, use `--ecmEnergy=13600.0`
  - Use `maxEvents` to adjust the number of events generated.
  - To adjust the mass of S (mS) or the Zd (mZd), simply change the name of the control script (`mc.MGPy8EG_ZdZd_4l_Signal_mS125_mZd30.py` will generate decays with mS=125 GeV and mZd=30 GeV).

Once the EVNT file has been created a truth derivation can be made (again assuming this is done on lxplus)
- Navigate to the gen_example folder from the generation step.
- `setupATLAS`
- `asetup Athena,main,latest`
- `Derivation_tf.py --CA True --inputEVNTFile tmp.EVNT.root --outputDAODFile truthDAOD.pool.root --formats TRUTH1`
  - If the derivation runs successfully the terminal output should end with 'exit code 0' and there should be a `truthDAOD.pool.root` file roughly the same size as `tmp.EVNT.root`.

More information about the official signal generation for the H/S -> XX/ZX -> 4l can be found in the JIRA tickets:
- H->ZdZd->4l: [JIRA](https://its.cern.ch/jira/browse/ATLMCPROD-11549)
- H->ZZd->4l: [JIRA](https://its.cern.ch/jira/browse/ATLMCPROD-11547)
