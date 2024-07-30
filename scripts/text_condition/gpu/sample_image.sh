CUDA_VISIBLE_DEVICES=0 python opensora/sample/sample_t2v.py \
    --model_path /storage/ongoing/new/7.19anyres/Open-Sora-Plan/bs16x8x1_img_29x480p_lr1e-4_snr5_noioff0.02_ema9999_dit_l_122_rope_mt5xxl_movie_panda_mj/checkpoint-2000/model_ema \
    --version 65x512x512 \
    --num_frames 1 \
    --height 480 \
    --width 640 \
    --cache_dir "../cache_dir" \
    --text_encoder_name google/mt5-xxl \
    --text_prompt examples/prompt_list_1.txt \
    --ae CausalVAEModel_D4_4x8x8 \
    --ae_path "/storage/dataset/488dim4_plus" \
    --save_img_path "sample_image_hw_dit_img_29x480p" \
    --fps 24 \
    --guidance_scale 2.0 \
    --num_sampling_steps 20 \
    --enable_tiling \
    --max_sequence_length 512 \
    --sample_method DPMSolverMultistep \
    --model_type dit \
    --save_memory