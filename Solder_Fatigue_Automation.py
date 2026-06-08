import os
import numpy as np
import pandas as pd

# AVOID THE WINDOWS GUI CRASH
import matplotlib
matplotlib.use('Agg') # Forces "Headless" image generation

import matplotlib.pyplot as plt
from ansys.mapdl.core import launch_mapdl

# ==============================================================================
# 0. TERMINAL CLEANUP & ENVIRONMENT PATHS
# ==============================================================================
os.system('cls' if os.name == 'nt' else 'clear')

BASE_DIR = r"D:\Priyan\Career\Python\Underfill_correct"
ORIGINAL_DAT = os.path.join(BASE_DIR, "Underfill_correct.dat")

# Exact Sync IDs assigned by Workbench
SOLDER_MAT_ID = 3
UNDERFILL_MAT_ID = 4

# ==============================================================================
# 1. PARAMETRIC DESIGN MATRIX REGISTRY
# ==============================================================================
solder_library = {
    "SAC305": {
        "constants": [30.88, 9543, 17432, 4.84, 0.6137, 16270, 33.5, 0.0052, 1.063],
        "two_ef_prime": 0.38, "c": -0.60
    },
    "SAC405": {
        "constants": [35.00, 7900, 40000, 4.20, 0.2300, 19500, 35.0, 0.0100, 1.600],
        "two_ef_prime": 0.42, "c": -0.58
    },
    "Innolot": {
        "constants": [50.00, 10500, 22000, 5.00, 0.4500, 21000, 42.5, 0.0085, 1.200],
        "two_ef_prime": 0.50, "c": -0.55
    }
}

underfill_library = {
    "Baseline_Epoxy": {
        "temps": [-40, 25, 75, 100, 125, 135, 150],
        "moduli": [9800, 9000, 8200, 7500, 6500, 4000, 800],
        "poissons": [0.30, 0.31, 0.32, 0.33, 0.34, 0.38, 0.45],
        "ctes": [24e-6, 25e-6, 27e-6, 29e-6, 32e-6, 45e-6, 75e-6]
    },
    "High_Performance_Filled": {
        "temps": [-40, 25, 75, 100, 125, 135, 150],
        "moduli": [15000, 14200, 13500, 12800, 11500, 9000, 2500],
        "poissons": [0.28, 0.29, 0.30, 0.31, 0.32, 0.34, 0.38],
        "ctes": [18e-6, 19e-6, 21e-6, 23e-6, 25e-6, 32e-6, 50e-6]
    }
}

compiled_results = []

# ==============================================================================
# 2. HELPER FUNCTION: CONSTRUCT CLEAN SANITIZED MATERIAL GENERATOR
# ==============================================================================
def build_complete_material_block(solder_props, uf_props):
    """Generates a comprehensive, clean materials database segment replacing all old cards."""
    block = [
        "/com,*********** Send Materials ***********",
        "! NATIVE MATERIAL 1 (PCB - FR-4)",
        "MP,DENS,1,1.84e-15", "MP,EX,1,20400", "MP,EY,1,18400", "MP,EZ,1,15000",
        "MP,PRXY,1,0.11", "MP,PRYZ,1,0.09", "MP,PRXZ,1,0.14",
        "MP,GXY,1,9200", "MP,GYZ,1,8400", "MP,GXZ,1,6600",
        "MP,ALPX,1,1.25e-05", "MP,ALPY,1,1.14e-05", "MP,ALPZ,1,8.2e-05",
        "MP,KXX,1,380000", "MP,KYY,1,380000", "MP,KZZ,1,300000",
        "",
        "! NATIVE MATERIAL 2 (Silicon Die)",
        "MP,DENS,2,2.33e-15", "MP,C,2,702000000000000", "MP,KXX,2,124000000",
        "MP,RSVX,2,1e-10", "MP,MURX,2,1",
        "MPTEMP,,,,,,,,", "MPTEMP,1,20,250,500,1000,1500",
        "MPDATA,ALPX,2,1,2.46e-06,3.61e-06,4.15e-06,4.44e-06,4.44e-06",
        "MPAMOD,2,22", "TB,ELASTIC,2,,,AELS",
        "TBDATA,1,166000,64000,64000,0,0,0", "TBDATA,7,166000,64000,0,0,0,166000",
        "TBDATA,13,0,0,0,80000,0,0", "TBDATA,19,80000,0,80000",
        "",
        "! PARAMETRIC MATERIAL 3 (Solder Bumps - Dynamic Anand Overwrite)",
        f"MP,ALPX,{SOLDER_MAT_ID},2.2e-05",
        f"MP,EX,{SOLDER_MAT_ID},4000",
        f"MP,NUXY,{SOLDER_MAT_ID},0.35",
        f"TB,RATE,{SOLDER_MAT_ID},1,9,ANAND"
    ]
    c = solder_props["constants"]
    block.append(f"TBDATA,1,{c[0]},{c[1]},{c[2]},{c[3]},{c[4]},{c[5]}")
    block.append(f"TBDATA,7,{c[6]},{c[7]},{c[8]}")
    
    block.extend([
        "",
        "! PARAMETRIC MATERIAL 4 (Underfill Table Overwrite)",
        "MPTEMP,,,,,,,,"
    ])
    for idx, t in enumerate(uf_props["temps"]):
        block.append(f"MPTEMP,{idx+1},{t}")
        
    block.append(f"MPDATA,EX,{UNDERFILL_MAT_ID},1,{','.join(map(str, uf_props['moduli'][:6]))}")
    if len(uf_props["moduli"]) > 6:
        block.append(f"MPDATA,EX,{UNDERFILL_MAT_ID},7,{','.join(map(str, uf_props['moduli'][6:]))}")
        
    block.append(f"MPDATA,NUXY,{UNDERFILL_MAT_ID},1,{','.join(map(str, uf_props['poissons'][:6]))}")
    if len(uf_props["poissons"]) > 6:
        block.append(f"MPDATA,NUXY,{UNDERFILL_MAT_ID},7,{','.join(map(str, uf_props['poissons'][6:]))}")
        
    block.append(f"MPDATA,ALPX,{UNDERFILL_MAT_ID},1,{','.join(map(str, uf_props['ctes'][:6]))}")
    if len(uf_props["ctes"]) > 6:
        block.append(f"MPDATA,ALPX,{UNDERFILL_MAT_ID},7,{','.join(map(str, uf_props['ctes'][6:]))}")
        
    block.append("/wb,mat,end")
    return "\n".join(block)

# ==============================================================================
# 3. RUN THE REFACTORED FASTER PIPELINE LOOP
# ==============================================================================
print("Booting Core MAPDL Engine Once (Faster Multi-Iteration Tracking)...")
mapdl = launch_mapdl(nproc=4, override=True)

try:
    with open(ORIGINAL_DAT, "r") as f:
        master_lines = f.readlines()

    for solder_name, solder_props in solder_library.items():
        for uf_name, uf_props in underfill_library.items():
            print(f"\n[SWEEP RUN] Combination Node: [{solder_name}] + [{uf_name}]")
            
            run_folder_name = f"{solder_name}_{uf_name}"
            iteration_run_dir = os.path.join(BASE_DIR, "sim_runs", run_folder_name)
            os.makedirs(iteration_run_dir, exist_ok=True)
            
            iteration_dat_path = os.path.join(iteration_run_dir, "Underfill_runtime_execution.dat")
            complete_material_block = build_complete_material_block(solder_props, uf_props)
            
            output_deck_lines = []
            skip_mode = False
            
            for line in master_lines:
                # Direct folder locking path rewrites
                if r"D:\Priyan\Career\new_solder_underfill_files" in line:
                    line = line.replace(r"D:\Priyan\Career\new_solder_underfill_files\dp0\global\MECH", iteration_run_dir)
                    line = line.replace(r"D:\Priyan\Career\new_solder_underfill_files\dp0\SYS-1\MECH\\", iteration_run_dir + os.sep)
                    line = line.replace(r"D:\Priyan\Career\new_solder_underfill_files\dp0\SYS-1\MECH", iteration_run_dir)
                
                u_line = line.upper().replace(" ", "")
                
                # Intercept the exact material start sequence card
                if "***********SENDMATERIALS***********" in u_line:
                    skip_mode = True
                    output_deck_lines.append(complete_material_block + "\n")
                    continue
                    
                if skip_mode:
                    if "/WB,MAT,END" in u_line:
                        skip_mode = False
                    continue
                    
                output_deck_lines.append(line)
                
            with open(iteration_dat_path, "w") as f:
                f.writelines(output_deck_lines)
            
            # Stable clear and reload loop structure
            mapdl.clear()
            print(" -> Solving native non-linear multi-step thermal cycles...")
            mapdl.input(iteration_dat_path)
            
            # --- Post-Processing Data Extraction ---
            print(" -> Extracting node fields from step cycles...")
            mapdl.post1()
            mapdl.cmsel("S", "BUMP")
            
            mapdl.set(time=7200)
            mapdl.etable("EPPL_7200", "EPPL", "EQV")
            mapdl.etable("VOL_7200", "VOLU")
            mapdl.smult("PROD_7200", "EPPL_7200", "VOL_7200")
            mapdl.ssum()
            avg_strain_7200 = mapdl.get_value("SSUM", 0, "ITEM", "PROD_7200") / mapdl.get_value("SSUM", 0, "ITEM", "VOL_7200")
            
            mapdl.set(time=9000)
            mapdl.etable("EPPL_9000", "EPPL", "EQV")
            mapdl.etable("VOL_9000", "VOLU")
            mapdl.smult("PROD_9000", "EPPL_9000", "VOL_9000")
            mapdl.ssum()
            avg_strain_9000 = mapdl.get_value("SSUM", 0, "ITEM", "PROD_9000") / mapdl.get_value("SSUM", 0, "ITEM", "VOL_9000")
            
            delta_epsilon_pl = avg_strain_9000 - avg_strain_7200
            
            two_ef = solder_props["two_ef_prime"]
            c_exp = solder_props["c"]
            N_f = 0.5 * ((delta_epsilon_pl / two_ef) ** (1 / c_exp))
            
            print(f" -> Result: Extracted Delta_E_pl = {delta_epsilon_pl:.6f} | Fatigue Life = {int(N_f)} Cycles")
            
            compiled_results.append({
                "Solder_Alloy": solder_name,
                "Underfill_Variant": uf_name,
                "Strain_Range": delta_epsilon_pl,
                "Fatigue_Life": int(N_f)
            })

except Exception as e:
    print(f"\n[CRITICAL ANALYSIS ERROR] Pipeline halted: {e}")

finally:
    print("\nShutting down MAPDL Engine core cleanly...")
    mapdl.exit()

# ==============================================================================
# 4. DATA PRESENTATION & CHART GENERATION
# ==============================================================================
if len(compiled_results) > 0:
    df = pd.DataFrame(compiled_results)
    print("\n================ DIRECT MATRIX OPTIMIZATION RESULTS ================")
    print(df.to_markdown(index=False))
    
    df.to_csv(os.path.join(BASE_DIR, "Packaging_Optimization_Sweeps.csv"), index=False)
    
    pivot_df = df.pivot(index='Solder_Alloy', columns='Underfill_Variant', values='Fatigue_Life')
    ax = pivot_df.plot(kind='bar', figsize=(10, 6), width=0.5, edgecolor='black', zorder=3)
    plt.yscale('log')
    plt.title('Package Reliability Array: Solder Alloy vs Underfill Matrix', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Solder Alloy Formulation', fontsize=12, labelpad=10)
    plt.ylabel('Predicted Thermal Fatigue Life Cycles (Log Scale)', fontsize=12, labelpad=10)
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle=':', alpha=0.7, zorder=0)
    plt.legend(title="Underfill Chemical Profiles", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.axhline(y=1000, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label="JEDEC Target (1000 Cycles)")
    plt.tight_layout()
    plt.savefig(os.path.join(BASE_DIR, 'package_matrix_optimization.png'), dpi=300)
    print(f"\nPipeline execution successful. Materials mapped cleanly without memory clashing.")