#!/bin/sh

export VIAME_INSTALL=/opt/noaa/viame
export VIDEO_DIRECTORY=videos
export SPECIES_LIST=pristipomoides_auricilla,pristipomoides_zonatus,pristipomoides_sieboldii,etelis_carbunculus,etelis_coruscans,naso,aphareus_rutilans,seriola,hyporthodus_quernus,caranx_melampygus

source ${VIAME_INSTALL}/setup_viame.sh

# Generate plots and video ingests
python ${VIAME_INSTALL}/configs/ingest_video.py --init -d ${VIDEO_DIRECTORY} \
  --detection-plots \
  -species ${SPECIES_LIST} \
  -threshold 0.25 -frate 2 -smooth 2 \
  -p ${VIAME_INSTALL}/configs/pipelines/ingest_video.mouss_count.pipe

# Timestamp adjustment hack (will be removed in future iterations), converts milliseconds to seconds
for f in database/*.kw18; do
    awk '{print $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18 / 1e6, $19, $20}' < ${f}.bckup > ${f}
done
