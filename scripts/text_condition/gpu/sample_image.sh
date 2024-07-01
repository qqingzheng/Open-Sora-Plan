CUDA_VISIBLE_DEVICES=0 python opensora/sample/sample_t2v.py \
    --model_path bs16_4node_480p_lr1e-4_snr5_noioff0.02_ema_rope_uditultra22_qknorm_ds22_mt5xxl_mjencn_czhan_humanimg/checkpoint-27500/model_ema \
    --version 65x512x512 \
    --num_frames 1 \
    --height 480 \
    --width 640 \
    --cache_dir "cache_dir" \
    --text_encoder_name google/mt5-xxl \
    --text_prompt examples/prompt_list_0.txt \
    --ae CausalVAEModel_4x8x8 \
    --ae_path "/storage/dataset/test140k" \
    --save_img_path "./sample_image_27500_cfg2.5_step20_480p_pos_neg_fp32" \
    --fps 24 \
    --guidance_scale 2.5 \
    --num_sampling_steps 20 \
    --sample_method DPMSolverMultistep \
    --model_3d \
    --enable_stable_fp32