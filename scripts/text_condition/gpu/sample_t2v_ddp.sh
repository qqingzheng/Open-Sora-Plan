# --save_img_path "./sample_video_26500ema_61x480p_k333_s122_cfg5.0_step50" \
# CUDA_VISIBLE_DEVICES=7 python opensora/sample/sample_t2v.py \
torchrun --nnodes=1 --nproc_per_node 8  --master_port 29503 \
    -m opensora.sample.sample_t2v_ddp \
    --model_path /storage/ongoing/new/7.19anyres/Open-Sora-Plan/bs16x8x1_img_29x480p_lr1e-4_snr5_noioff0.02_ema9999_dit_l_122_rope_mt5xxl_movie_panda_mj \
    --version 65x512x512 \
    --num_frames 29 \
    --height 480 \
    --width 640 \
    --cache_dir "../cache_dir" \
    --text_encoder_name google/mt5-xxl \
    --text_prompt examples/prompt_list_0.txt \
    --ae CausalVAEModel_D4_4x8x8 \
    --ae_path "/storage/dataset/488dim4_plus" \
    --save_img_path "./sample_video_dit_img_29x480p" \
    --fps 24 \
    --guidance_scale 7.5 \
    --num_sampling_steps 50 \
    --enable_tiling \
    --tile_overlap_factor 0.125 \
    --max_sequence_length 512 \
    --sample_method EulerAncestralDiscrete \
    --model_type "dit"