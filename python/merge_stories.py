import os
import subprocess
from pathlib import Path

stories_dir = Path("/Users/xuqiangfang/Downloads/video-stories")
merged_dir = Path("/Users/xuqiangfang/Downloads/video-stories-merged")
merged_dir.mkdir(parents=True, exist_ok=True)

volumes = []
volumes.append((1, 1, 95))
start = 96
for vol_num in range(2, 15):
    end = start + 94 - 1
    volumes.append((vol_num, start, end))
    start = end + 1

assert volumes[-1][2] == 1317, f"Last story is not 1317, got {volumes[-1][2]}"

temp_manifests = []
success_count = 0

try:
    for vol_num, s, e in volumes:
        vol_str = f"{vol_num:02d}"
        s_str = f"{s:04d}"
        e_str = f"{e:04d}"
        
        output_filename = f"volume-{vol_str}-stories-{s_str}-{e_str}.mp4"
        output_path = merged_dir / output_filename
        tmp_output_path = merged_dir / f"{output_filename}.tmp.mp4"
        
        manifest_path = merged_dir / f"temp-volume-{vol_str}.txt"
        temp_manifests.append(manifes        temp_manifests.append(manifes        temp_ma") as         st        temp_manr         temp_manifests.
                                                                 
                                                                    se F                                       _file}")
                                   file  {story_fi                           
               
                                                                       "0                                                                       "0      "                  start",
            "-y",
            "-y",
       t_path)
                                  "Merging Volume {vol_str} (st                       })...")
                                                                      ocess.PIP                                             
                                                                       (res.stderr                                                              ol_s                                                                       (res.stderr                                                              out                                                              created: {output_filename}")
            success_count += 1
        else:
            raise FileNotFoundError(f"Expected tem            raise FileNotFoundError(f"Expected tem              for manifest_path in temp_mani            raise FileNotFoundError(f"Expected tem            raise FileNotFoundError(f"Expected tem              for manifest_path in temp_mani            raise FileNotFoundE ind            raish}            rais              rol            raise FileNotFoundError(f"Expected tem            raise FileNotFoundError(f"Expe e            raise FileNotFoundError(f"Expected tem            raise FileNotFoundError(f"Expected tem              f = merged_dir / f"{output_filename}.tmp.mp4"
        if tmp_output_path.is_file():
            try:
                tmp_output_path.unlink()
            except Exception as ex:
                print(f"Failed to delete tmp {tmp_output_path}: {ex}")

print(f"\nAll 14 completed? {'Yes' if success_count == len(volumes) else 'No'}. Created {success_count} volumes.")
