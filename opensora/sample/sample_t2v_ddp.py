import math
import os
import torch
import argparse
import torchvision
import torch.distributed as dist

from diffusers.schedulers import (DDIMScheduler, DDPMScheduler, PNDMScheduler,
                                  EulerDiscreteScheduler, DPMSolverMultistepScheduler,
                                  HeunDiscreteScheduler, EulerAncestralDiscreteScheduler,
                                  DEISMultistepScheduler, KDPM2AncestralDiscreteScheduler)
from diffusers.schedulers.scheduling_dpmsolver_singlestep import DPMSolverSinglestepScheduler
from diffusers.models import AutoencoderKL, AutoencoderKLTemporalDecoder, Transformer2DModel
from omegaconf import OmegaConf
from torchvision.utils import save_image
from transformers import T5EncoderModel, T5Tokenizer, AutoTokenizer, MT5EncoderModel

import os, sys

from opensora.models.causalvideovae import ae_stride_config, ae_wrapper

from opensora.models.diffusion.opensora_v1_2.modeling_opensora import OpenSoraT2V_v1_2
# from opensora.models.diffusion.latte.modeling_latte import LatteT2V
# from opensora.models.captioner.refiner import model_gen

from opensora.models.text_encoder import get_text_enc
from opensora.utils.utils import save_video_grid

from opensora.sample.pipeline_opensora import OpenSoraPipeline, OpenSoraFreeInitPipeline

import imageio

try:
    import torch_npu
    from opensora.npu_config import npu_config
except:
    torch_npu = None
    npu_config = None
    pass
import time



def load_t2v_checkpoint(model_path):
    if args.version == 'v1_2':
        transformer_model = OpenSoraT2V_v1_2.from_pretrained(model_path, cache_dir=args.cache_dir,
                                                        low_cpu_mem_usage=False, device_map=None,
                                                        torch_dtype=weight_dtype)
    elif args.version == 'v1_5':
        transformer_model = OpenSoraT2V_v1_5.from_pretrained(model_path, cache_dir=args.cache_dir,
                                                        low_cpu_mem_usage=False, device_map=None,
                                                        torch_dtype=weight_dtype)
    # set eval mode
    transformer_model.eval()
    pipeline = OpenSoraPipeline(
        vae=vae,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        scheduler=scheduler,
        transformer=transformer_model
    ).to(device)

    if args.compile:
        # 4%
        pipeline.transformer = torch.compile(pipeline.transformer)
    return pipeline


def get_latest_path():
    # Get the most recent checkpoint
    dirs = os.listdir(args.model_path)
    dirs = [d for d in dirs if d.startswith("checkpoint")]
    dirs = sorted(dirs, key=lambda x: int(x.split("-")[1]))
    path = dirs[-1] if len(dirs) > 0 else None

    return path


def run_model_and_save_images(pipeline, model_path):
    video_grids = []
    if not isinstance(args.text_prompt, list):
        args.text_prompt = [args.text_prompt]
    if len(args.text_prompt) == 1 and args.text_prompt[0].endswith('txt'):
        text_prompt = open(args.text_prompt[0], 'r').readlines()
        args.text_prompt = [i.strip() for i in text_prompt]

    checkpoint_name = f"{os.path.basename(model_path)}"

    positive_prompt = """
    masterpiece, high quality, ultra-detailed, 
    {}. 
    emotional, harmonious, vignette, 4k epic detailed, shot on kodak, 35mm photo, 
    sharp focus, high budget, cinemascope, moody, epic, gorgeous
    """
    
    positive_prompt = """
    high quality, high aesthetic, {}
    """

    negative_prompt = """
    nsfw, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, 
    low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry.
    """
    

    for index, prompt in enumerate(args.text_prompt):
        if index % world_size != local_rank:
            continue
        if args.refine_caption:
            q = f'Translate this brief generation prompt into a detailed caption: {prompt}'
            query = f'[UNUSED_TOKEN_146]user\n{q}[UNUSED_TOKEN_145]\n[UNUSED_TOKEN_146]assistant\n'
            # print(query)
            with torch.cuda.amp.autocast(): 
                refine_prompt = model_gen(refiner, query, None)
            refine_prompt = refine_prompt.replace('<|im_end|>', '').replace('</s>', '')
            input_prompt = positive_prompt.format(refine_prompt)
            print(f'Processing the origin prompt({prompt})\n  '
                  f'refine_prompt ({refine_prompt})\n  input_prompt ({input_prompt})\n  device ({device})')
        else:
            input_prompt = positive_prompt.format(prompt)
            print(f'Processing the origin prompt({prompt})\n  '
                  f'input_prompt ({input_prompt})\n device ({device})')
        videos = pipeline(
            input_prompt, 
                          negative_prompt=negative_prompt, 
                          num_frames=args.num_frames,
                          height=args.height,
                          width=args.width,
                          motion_score=args.motion_score, 
                          num_inference_steps=args.num_sampling_steps,
                          guidance_scale=args.guidance_scale,
                          num_samples_per_prompt=args.num_samples_per_prompt,
                          mask_feature=True,
                          device=args.device,
                          max_sequence_length=args.max_sequence_length,
                          ).images
        print('videos.shape', videos.shape)
        if args.num_frames == 1:
            videos = videos[:, 0].permute(0, 3, 1, 2)  # b t h w c -> b c h w
            save_image(videos / 255.0, os.path.join(args.save_img_path,
                                                    f'{model_path}', f'{args.sample_method}_{index}_{checkpoint_name}_gs{args.guidance_scale}_s{args.num_sampling_steps}_m{args.motion_score}.{ext}'),
                        nrow=1, normalize=True, value_range=(0, 1))  # t c h w
            print('save done...')

        else:
            if args.num_samples_per_prompt == 1:
                imageio.mimwrite(
                    os.path.join(
                        args.save_img_path,
                        f'{model_path}', f'{args.sample_method}_{index}_{checkpoint_name}_gs{args.guidance_scale}_s{args.num_sampling_steps}_m{args.motion_score}.{ext}'
                    ), videos[0],
                    fps=args.fps, quality=6)  # highest quality is 10, lowest is 0
                print('save done...')
            else:
                for i in range(args.num_samples_per_prompt):
                    print(f'save i {i}')
                    imageio.mimwrite(
                        os.path.join(
                            args.save_img_path,
                            f'{model_path}', f'{args.sample_method}_{index}_{checkpoint_name}_gs{args.guidance_scale}_s{args.num_sampling_steps}_m{args.motion_score}_i{i}.{ext}'
                        ), videos[i],
                        fps=args.fps, quality=6)  # highest quality is 10, lowest is 0
                videos = save_video_grid(videos)
                print(f'save total video_grids {videos.shape}')
                imageio.mimwrite(
                    os.path.join(
                        args.save_img_path,
                        f'{model_path}', f'{args.sample_method}_{index}_{checkpoint_name}_gs{args.guidance_scale}_s{args.num_sampling_steps}_m{args.motion_score}.{ext}'
                    ), videos,
                    fps=args.fps, quality=6)  # highest quality is 10, lowest is 0)

        video_grids.append(videos)
    dist.barrier()
    video_grids = torch.cat(video_grids, dim=0).cuda()
    shape = list(video_grids.shape)
    shape[0] *= world_size
    gathered_tensor = torch.zeros(shape, dtype=video_grids.dtype, device=device)
    dist.all_gather_into_tensor(gathered_tensor, video_grids.contiguous())
    video_grids = gathered_tensor.cpu()

    # video_grids = video_grids.repeat(world_size, 1, 1, 1)
    # output = torch.zeros(video_grids.shape, dtype=video_grids.dtype, device=device)
    # dist.all_to_all_single(output, video_grids)
    # video_grids = output.cpu()
    def get_file_name():
        return os.path.join(args.save_img_path,
                            f'{args.sample_method}_gs{args.guidance_scale}_s{args.num_sampling_steps}_m{args.motion_score}_{checkpoint_name}.{ext}')
    
    if local_rank == 0:
        if args.num_frames == 1:
            save_image(video_grids / 255.0, get_file_name(),
                    nrow=math.ceil(math.sqrt(len(video_grids))), normalize=True, value_range=(0, 1))
        else:
            video_grids = save_video_grid(video_grids)
            imageio.mimwrite(get_file_name(), video_grids, fps=args.fps, quality=6)

    print('save path {}'.format(args.save_img_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, default='LanguageBind/Open-Sora-Plan-v1.0.0')
    parser.add_argument("--version", type=str, default='v1_2', choices=['v1_2', 'v1_5'])
    parser.add_argument("--num_frames", type=int, default=1)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--device", type=str, default='cuda:0')
    parser.add_argument("--cache_dir", type=str, default='./cache_dir')
    parser.add_argument("--ae", type=str, default='CausalVAEModel_4x8x8')
    parser.add_argument("--ae_path", type=str, default='CausalVAEModel_4x8x8')
    parser.add_argument("--text_encoder_name", type=str, default='DeepFloyd/t5-v1_1-xxl')
    parser.add_argument("--save_img_path", type=str, default="./sample_videos/t2v")
    parser.add_argument("--guidance_scale", type=float, default=7.5)
    parser.add_argument("--sample_method", type=str, default="PNDM")
    parser.add_argument("--num_sampling_steps", type=int, default=50)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--max_sequence_length", type=int, default=512)
    parser.add_argument("--text_prompt", nargs='+')
    parser.add_argument('--tile_overlap_factor', type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num_samples_per_prompt", type=int, default=1)
    parser.add_argument('--enable_tiling', action='store_true')
    parser.add_argument('--refine_caption', action='store_true')
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--save_memory', action='store_true')
    parser.add_argument('--motion_score', type=float, default=None)    
    parser.add_argument("--prediction_type", type=str, default='epsilon', help="The prediction_type that shall be used for training. Choose between 'epsilon' or 'v_prediction' or leave `None`. If left to `None` the default prediction type of the scheduler: `noise_scheduler.config.prediciton_type` is chosen.")
    parser.add_argument('--rescale_betas_zero_snr', action='store_true')
    args = parser.parse_args()

    if torch_npu is not None:
        npu_config.print_msg(args)

    # 初始化分布式环境
    local_rank = int(os.getenv('RANK', 0))
    world_size = int(os.getenv('WORLD_SIZE', 1))
    print('world_size', world_size)
    if torch_npu is not None and npu_config.on_npu:
        torch_npu.npu.set_device(local_rank)
    else:
        torch.cuda.set_device(local_rank)
    dist.init_process_group(backend='nccl', init_method='env://', world_size=world_size, rank=local_rank)

    torch.manual_seed(args.seed)
    weight_dtype = torch.bfloat16
    device = torch.cuda.current_device()
    vae = ae_wrapper[args.ae](args.ae_path)
    print(args.ae)
    vae.vae = vae.vae.to(device=device, dtype=weight_dtype)
    if args.enable_tiling:
        vae.vae.enable_tiling()
        vae.vae.tile_overlap_factor = args.tile_overlap_factor
        vae.vae.tile_sample_min_size = 512
        vae.vae.tile_latent_min_size = 64
        vae.vae.tile_sample_min_size_t = 29
        vae.vae.tile_latent_min_size_t = 8
        if args.save_memory:
            vae.vae.tile_sample_min_size = 256
            vae.vae.tile_latent_min_size = 32
            vae.vae.tile_sample_min_size_t = 29
            vae.vae.tile_latent_min_size_t = 8
    vae.vae_scale_factor = ae_stride_config[args.ae]

    text_encoder = MT5EncoderModel.from_pretrained("/storage/ongoing/new/Open-Sora-Plan/cache_dir/mt5-xxl", 
                                                   cache_dir=args.cache_dir, low_cpu_mem_usage=True, 
                                                   torch_dtype=weight_dtype).to(device)
    tokenizer = AutoTokenizer.from_pretrained("/storage/ongoing/new/Open-Sora-Plan/cache_dir/mt5-xxl", 
                                              cache_dir=args.cache_dir)
    # text_encoder = T5EncoderModel.from_pretrained("/storage/ongoing/new/Open-Sora-Plan/cache_dir/models--DeepFloyd--t5-v1_1-xxl/snapshots/c9c625d2ec93667ec579ede125fd3811d1f81d37", cache_dir=args.cache_dir, low_cpu_mem_usage=True, torch_dtype=weight_dtype)
    # tokenizer = AutoTokenizer.from_pretrained("/storage/ongoing/new/Open-Sora-Plan/cache_dir/models--DeepFloyd--t5-v1_1-xxl/snapshots/c9c625d2ec93667ec579ede125fd3811d1f81d37", cache_dir=args.cache_dir)
    
    # text_encoder = T5EncoderModel.from_pretrained(args.text_encoder_name, cache_dir=args.cache_dir,
    #                                               low_cpu_mem_usage=True, torch_dtype=weight_dtype).to(device)
    # tokenizer = T5Tokenizer.from_pretrained(args.text_encoder_name, cache_dir=args.cache_dir)
    if args.refine_caption:
        from transformers import AutoModel, AutoTokenizer
        new_path = '/storage/zhubin/ShareGPT4Video/sharegpt4video/sharecaptioner_v1'
        refiner_tokenizer = AutoTokenizer.from_pretrained(new_path, trust_remote_code=True)
        refiner = AutoModel.from_pretrained(new_path, torch_dtype=weight_dtype, trust_remote_code=True).eval()
        refiner.to(device)
        refiner.tokenizer = refiner_tokenizer

    # set eval mode
    vae.eval()
    text_encoder.eval()

    if args.sample_method == 'DDIM':  #########
        scheduler = DDIMScheduler(clip_sample=False, prediction_type=args.prediction_type, rescale_betas_zero_snr=args.rescale_betas_zero_snr, timestep_spacing="trailing")
    elif args.sample_method == 'EulerDiscrete':
        scheduler = EulerDiscreteScheduler()
    elif args.sample_method == 'DDPM':  #############
        scheduler = DDPMScheduler(clip_sample=False)
    elif args.sample_method == 'DPMSolverMultistep':
        scheduler = DPMSolverMultistepScheduler()
    elif args.sample_method == 'DPMSolverSinglestep':
        scheduler = DPMSolverSinglestepScheduler()
    elif args.sample_method == 'PNDM':
        scheduler = PNDMScheduler()
    elif args.sample_method == 'HeunDiscrete':  ########
        scheduler = HeunDiscreteScheduler()
    elif args.sample_method == 'EulerAncestralDiscrete':
        scheduler = EulerAncestralDiscreteScheduler(prediction_type=args.prediction_type, rescale_betas_zero_snr=args.rescale_betas_zero_snr, timestep_spacing="trailing")
    elif args.sample_method == 'DEISMultistep':
        scheduler = DEISMultistepScheduler()
    elif args.sample_method == 'KDPM2AncestralDiscrete':  #########
        scheduler = KDPM2AncestralDiscreteScheduler()

    if not os.path.exists(args.save_img_path):
        os.makedirs(args.save_img_path, exist_ok=True)

    if args.num_frames == 1:
        video_length = 1
        ext = 'jpg'
    else:
        ext = 'mp4'

    latest_path = None
    save_img_path = args.save_img_path
    # while True:
    #     cur_path = get_latest_path()
    #     # print(cur_path, latest_path)
    #     if cur_path == latest_path:
    #         time.sleep(5)
    #         continue

    #     time.sleep(1)
    #     latest_path = cur_path
    #     os.makedirs(os.path.join(args.save_img_path, latest_path), exist_ok=True)
    #     if npu_config is not None:
    #         npu_config.print_msg(f"The latest_path is {latest_path}")
    #     else:
    #         print(f"The latest_path is {latest_path}")
    if latest_path is None:
        latest_path = ''

    full_path = f"{args.model_path}"
    # full_path = f"{args.model_path}/{latest_path}/model_ema"
    # full_path = f"{args.model_path}/{latest_path}/model"
    try:
        pipeline = load_t2v_checkpoint(full_path)
    except:
        time.sleep(100)
        pipeline = load_t2v_checkpoint(full_path)
    # print('load model')
    if npu_config is not None and npu_config.on_npu and npu_config.profiling:
        experimental_config = torch_npu.profiler._ExperimentalConfig(
            profiler_level=torch_npu.profiler.ProfilerLevel.Level1,
            aic_metrics=torch_npu.profiler.AiCMetrics.PipeUtilization
        )
        profile_output_path = "/home/image_data/npu_profiling_t2v"
        os.makedirs(profile_output_path, exist_ok=True)

        with torch_npu.profiler.profile(
                activities=[torch_npu.profiler.ProfilerActivity.NPU, torch_npu.profiler.ProfilerActivity.CPU],
                with_stack=True,
                record_shapes=True,
                profile_memory=True,
                experimental_config=experimental_config,
                schedule=torch_npu.profiler.schedule(wait=10000, warmup=0, active=1, repeat=1,
                                                        skip_first=0),
                on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(f"{profile_output_path}/")
        ) as prof:
            run_model_and_save_images(pipeline, latest_path)
            prof.step()
    else:
        # print('gpu')
        run_model_and_save_images(pipeline, latest_path)
