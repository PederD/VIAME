
#!/bin/sh

# Setup VIAME Paths (no need to run multiple times if you already ran it)

source ../../setup_viame.sh

# Run score tracks on data for singular metrics

score_tracks \
  --hadwav --fn2ts \       # Scoring options, use frames not timestamps
  --computed-tracks detections.kw18 \  # Computed tracks
  --truth-tracks groundtruth.kw18 \  # Groundtruth (annotated) tracks
  > score_tracks_output.txt   # Output file

# Generate ROC

score_events \
  --computed-tracks detections.kw18 \
  --truth-tracks groundtruth.kw18 \
  --fn2ts --kw19-hack --gt-prefiltered --ct-prefiltered \
  --roc-dump roc.plot

# Plot ROC

python plotroc.py roc.plot
