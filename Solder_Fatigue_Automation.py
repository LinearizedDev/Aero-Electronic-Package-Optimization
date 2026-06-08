import os
import matplotlib
matplotlib.use('Agg') # Keep headless for batch processing runs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ansys.mapdl.core import launch_mapdl

# --- Env setup & Target paths ---
os.system('cls' if os.name == 'nt' else 'clear')

WORKING_DIR = r"D:\Priyan\Career\Python\Underfill_correct"
MASTER_DECK = os.path.join(WORKING_DIR, "Underfill_correct.dat")

# Hardcoded material IDs mapped from the Workbench mesh assignment
SOLDER_ID = 3
UF_ID = 4

# --- Material Matrix ---
solder_db = {
    "SAC305": {
        "anand": [30.88, 9543, 17432, 4.84, 0.6137, 16270, 33.5, 0.0052, 1.063],
        "two_ef": 0.38, "c_exp": -0.60
    },
    "SAC405": {
        "anand": [35.00, 7900, 40000, 4.20, 0.2300, 19500, 35.0, 0.0100, 1.600],
        "two_ef": 0.42, "c_exp": -0.58
    },
    "Innolot": {
        "anand": [50.00, 10500, 22000, 5.00, 0.4500, 21000, 42.5, 0.0085, 1.200],
        "two_ef": 0.50, "c_exp": -0.55
    }
}

underfill_db = {
    "Baseline_Epoxy": {
        "t_arr": [-40, 25, 75, 100, 125, 135, 150],
        "ex_arr": [9800, 9000, 8200, 7500, 6500, 4000, 800],
        "nuxy_arr": [0.30, 0.31, 0.32, 0.33, 0.34, 0.38, 0.45],
        "alpx_arr": [24e-6, 25e-6, 27e-6, 29e-6, 32e-6, 45e-6, 75e-6]
    },
    "High_Performance_Filled": {
        "t_arr": [-40, 25, 75, 100, 125, 135, 150],
        "ex_arr": [15000, 14200, 13500, 12800, 11500, 9000, 2500],
        "nuxy_arr": [0.28, 0.29, 0.30, 0.31, 0.32, 0.34, 0.38],
        "alpx_arr": [18e-6, 19e-6, 21e-6, 23e-6, 25e-6, 32e-6, 50e-6]
    }
}

run_matrix_log = []

def generate_material_cards(solder_props, uf_props):
    """
    Compiles a clean APDL material block to drop into the solver stream.
    Splits the 7-point temp arrays to obey APDL's strict 6-value line limit.
    """
    card_lines = [
        "/com,*********** Send Materials ***********",
        "! Material 1: Default FR-4 Base Mat",
        "MP,DENS,1,1.84e-15", "MP,EX,1,20400", "MP,EY,1,18400", "MP,EZ,1,15000",
        "MP,PRXY,1,0.11", "MP,PRYZ,1,0.09", "MP,PRXZ,1,0.14",
        "MP,GXY,1,9200", "MP,GYZ,1,8400", "MP,GXZ,1,6600",
        "MP,ALPX,1,1.25e-05", "MP,ALPY,1,1.14e-05", "MP,ALPZ,1,8.2e-05",
        "MP,KXX,1,380000", "MP,KYY,1,380000", "MP,KZZ,1,300000",
        "",
        "! Material 2: Silicon Chip",
        "MP,DENS,2,2.33e-15", "MP,C,2,702000000000000", "MP,KXX,2,124000000",
        "MP,RSVX,2,1e-10", "MP,MURX,2,1",
        "MPTEMP,,,,,,,,", "MPTEMP,1,20,250,500,1000,1500",
        "MPDATA,ALPX,2,1,2.46e-06,3.61e-06,4.15e-06,4.44e-06,4.44e-06",
        "MPAMOD,2,22", "TB,ELASTIC,2,,,AELS",
        "TBDATA,1,166000,64000,64000,0,0,0", "TBDATA,7,166000,64000,0,0,0,166000",
        "TBDATA,13,0,0,0,80000,0,0", "TBDATA,19,80000,0,80000",
        "",
        f"! Material {SOLDER_ID}: Solder Array (Viscoplastic Creep - Anand Overwrite)",
        f"MP,ALPX,{SOLDER_ID},2.2e-05",
        f"MP,EX,{SOLDER_ID},4000",
        f"MP,NUXY,{SOLDER_ID},0.35",
        f"TB,RATE,{SOLDER_ID},1,9,ANAND"
    ]
    
    c = solder_props["anand"]
    card_lines.append(f"TBDATA,1,{c[0]},{c[1]},{c[2]},{c[3]},{c[4]},{c[5]}")
    card_lines.append(f"TBDATA,7,{c[6]},{c[7]},{c[8]}")
    
    card_lines.extend([
        "",
        f"! Material {UF_ID}: Underfill Compound Matrix (Temp-Dependent Tables)",
        "MPTEMP,,,,,,,,"
    ])
    
    for i, t in enumerate(uf_props["t_arr"]):
        card_lines.append(f"MPTEMP,{i+1},{t}")
        
    # Slicing vectors to handle APDL line buffer limits (Max 6 tokens per line)
    card_lines.append(f"MPDATA,EX,{UF_ID},1,{','.join(map(str, uf_props['ex_arr'][:6]))}")
    if len(uf_props["ex_arr"]) > 6:
        card_lines.append(f"MPDATA,EX,{UF_ID},7,{','.join(map(str, uf_props['ex_arr'][6:]))}")
        
    card_lines.append(f"MPDATA,NUXY,{UF_ID},1,{','.join(map(str, uf_props['nuxy_arr'][:6]))}")
    if len(uf_props["nuxy_arr"]) > 6:
        card_lines.append(f"MPDATA,NUXY,{UF_ID},7,{','.join(map(str, uf_props['nuxy_arr'][6:]))}")
        
    card_lines.append(f"MPDATA,ALPX,{UF_ID},1,{','.join(map(str, uf_props['alpx_arr'][:6]))}")
    if len(uf_props["alpx_arr"]) > 6:
        card_lines.append(f"MPDATA,ALPX,{UF_ID},7,{','.join(map(str, uf_props['alpx_arr'][6:]))}")
        
    card_lines.append("/wb,mat,end")
    return "\n".join(card_lines)


# --- Initialize MAPDL Instance ---
print("Spinning up background MAPDL solver core (4-threaded license allocation)...")
mapdl = launch_mapdl(nproc=4, override=True)

try:
    with open(MASTER_DECK, "r") as f:
        master_data_lines = f.readlines()

    # --- Sweep Loop Iteration Execution ---
    for s_name, s_vals in solder_db.items():
        for uf_name, uf_vals in underfill_db.items():
            print(f">> Processing Matrix Design Point: {s_name} + {uf_name}")
            
            # Setup isolated run directories to prevent solver file locking conflicts
            run_id = f"{s_name}_{uf_name}"
            scratch_path = os.path.join(WORKING_DIR, "sim_runs", run_id)
            os.makedirs(scratch_path, exist_ok=True)
            
            target_deck = os.path.join(scratch_path, "Underfill_runtime_execution.dat")
            injected_materials = generate_material_cards(s_vals, uf_vals)
            
            sanitized_lines = []
            strip_active = False
            
            # State-machine stream parser to swap material database cards
            for line in master_data_lines:
                # Redirect relative directory pointers for the execution cluster
                if r"D:\Priyan\Career\new_solder_underfill_files" in line:
                    line = line.replace(r"D:\Priyan\Career\new_solder_underfill_files\dp0\global\MECH", scratch_path)
                    line = line.replace(r"D:\Priyan\Career\new_solder_underfill_files\dp0\SYS-1\MECH\\", scratch_path + os.sep)
                    line = line.replace(r"D:\Priyan\Career\new_solder_underfill_files\dp0\SYS-1\MECH", scratch_path)
                
                norm_line = line.upper().replace(" ", "")
                
                if "***********SENDMATERIALS***********" in norm_line:
                    strip_active = True
                    sanitized_lines.append(injected_materials + "\n")
                    continue
                    
                if strip_active:
                    if "/WB,MAT,END" in norm_line:
                        strip_active = False
                    continue
                    
                sanitized_lines.append(line)
                
            with open(target_deck, "w") as f:
                f.writelines(sanitized_lines)
            
            mapdl.clear()
            print("   Executing non-linear thermal cycling increments...")
            mapdl.input(target_deck)
            
            mapdl.post1()
            mapdl.cmsel("S", "BUMP") # Focus evaluation strictly on the solder bumps
            
            # Extraction point A: Cycle 1 Hot Dwell completion
            mapdl.set(time=7200)
            mapdl.etable("E_PL_1", "EPPL", "EQV")
            mapdl.etable("V_1", "VOLU")
            mapdl.smult("P_1", "E_PL_1", "V_1")
            mapdl.ssum()
            avg_strain_1 = mapdl.get_value("SSUM", 0, "ITEM", "P_1") / mapdl.get_value("SSUM", 0, "ITEM", "V_1")
            
            # Extraction point B: Cycle 2 Hot Dwell completion
            mapdl.set(time=9000)
            mapdl.etable("E_PL_2", "EPPL", "EQV")
            mapdl.etable("V_2", "VOLU")
            mapdl.smult("P_2", "E_PL_2", "V_2")
            mapdl.ssum()
            avg_strain_2 = mapdl.get_value("SSUM", 0, "ITEM", "P_2") / mapdl.get_value("SSUM", 0, "ITEM", "V_2")
            
            # Calculate volume-averaged plastic strain increment
            strain_increment = avg_strain_2 - avg_strain_1
            
            # Coffin-Manson low-cycle fatigue life tracking
            cycles = 0.5 * ((strain_increment / s_vals["two_ef"]) ** (1 / s_vals["c_exp"]))
            print(f"   Metrics: Plastic Strain Delta = {strain_increment:.6f} -> Predicted Life = {int(cycles)} Cycles")
            
            run_matrix_log.append({
                "Solder_Alloy": s_name,
                "Underfill_Variant": uf_name,
                "Strain_Range": strain_increment,
                "Fatigue_Life": int(cycles)
            })

except Exception as err:
    print(f"\n[PIPELINE EXCEPTION FAILURE] Execution halted: {err}")

finally:
    print("\nReleasing MAPDL solver engine licenses...")
    mapdl.exit()

# --- Post-run Data Reporting & Plotting ---
if run_matrix_log:
    results_df = pd.DataFrame(run_matrix_log)
    results_df.to_csv(os.path.join(WORKING_DIR, "Packaging_Optimization_Sweeps.csv"), index=False)
    
    pivot_table = results_df.pivot(index='Solder_Alloy', columns='Underfill_Variant', values='Fatigue_Life')
    
    # Render reliability array visualization dashboard
    ax = pivot_table.plot(kind='bar', figsize=(10, 6), width=0.5, edgecolor='black', zorder=3)
    plt.yscale('log')
    plt.title('Package Reliability Array: Solder Alloy vs Underfill Matrix', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('Solder Alloy Formulation', fontsize=12, labelpad=10)
    plt.ylabel('Predicted Thermal Fatigue Life Cycles (Log Scale)', fontsize=12, labelpad=10)
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle=':', alpha=0.7, zorder=0)
    plt.legend(title="Underfill Chemical Profiles", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.axhline(y=1000, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label="JEDEC Qualification Target")
    plt.tight_layout()
    
    plt.savefig(os.path.join(WORKING_DIR, 'package_matrix_optimization.png'), dpi=300)
    print("\nArray visualization complete. Datasets and plot synced cleanly to local storage.")
