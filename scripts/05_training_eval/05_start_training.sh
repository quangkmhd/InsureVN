#!/bin/bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
echo "Waiting for Oumi to be installed..."
while ! command -v oumi &> /dev/null; do
  sleep 5
done
echo "Oumi is installed! Starting training..."
PYTHONUNBUFFERED=1 oumi train -c configs/oumi/train_qwen3_vl_4b.yaml 2>&1 | tee training_monitor.log
