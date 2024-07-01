export WANDB_KEY="953e958793b218efb850fa194e85843e2c3bd88b"
# export WANDB_MODE="offline"
export ENTITY="linbin"
export PROJECT="bs32_4node_240p_lr2e-5_snr5_noioff0.02_ema_udit22_ds22_mt5xxl"
export HF_DATASETS_OFFLINE=1 
export TRANSFORMERS_OFFLINE=1
# NCCL setting
export PDSH_RCMD_TYPE=ssh
export NCCL_PXN_DISABLE=0
export NCCL_IB_QPS_PER_CONNECTION=4
export NCCL_IB_GID_INDEX=3
export NCCL_ALGO=Ring
export OMP_NUM_THREADS=1

accelerate launch \
    --config_file scripts/accelerate_configs/multi_node_example.yaml \
    opensora/train/train_t2v_diffusers.py \
    --model UDiTT2V-L/122 \
    --text_encoder_name google/mt5-xxl \
    --cache_dir "./cache_dir" \
    --dataset t2v \
    --ae CausalVAEModel_4x8x8 \
    --ae_path "/storage/dataset/test140k" \
    --video_data "scripts/train_data/video_data.txt" \
    --image_data "scripts/train_data/image_data.txt" \
    --sample_rate 1 \
    --num_frames 1 \
    --max_height 240 \
    --max_width 320 \
    --interpolation_scale_t 1.0 \
    --interpolation_scale_h 0.5 \
    --interpolation_scale_w 0.5 \
    --attention_mode xformers \
    --gradient_checkpointing \
    --train_batch_size=32 \
    --dataloader_num_workers 10 \
    --gradient_accumulation_steps=1 \
    --max_train_steps=1000000 \
    --learning_rate=2e-5 \
    --lr_scheduler="constant" \
    --lr_warmup_steps=0 \
    --mixed_precision="bf16" \
    --report_to="wandb" \
    --checkpointing_steps=500 \
    --output_dir="bs32_4node_240p_lr2e-5_snr5_noioff0.02_ema_udit22_ds22_mt5xxl" \
    --allow_tf32 \
    --model_max_length 512 \
    --use_image_num 0 \
    --enable_tracker \
    --snr_gamma 5.0 \
    --use_ema \
    --ema_start_step 0 \
    --cfg 0.1 \
    --noise_offset 0.02 \
    --downsampler "k33_s22"  \
    --resume_from_checkpoint="latest" \
    --pretrained "/storage/ongoing/new/Open-Sora-Plan/bs64_4node_240p_lr1e-4_snr5_noioff0.02_ema_udit22_ds22_mt5xxl/checkpoint-19500/model/diffusion_pytorch_model.safetensors"