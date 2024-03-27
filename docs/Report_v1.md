# Open-Sora Causal Video VAE Report

## Examples

### Image Reconstruction


## Image Reconstruction

<img src="https://github.com/PKU-YuanGroup/Open-Sora-Plan/assets/88202804/1684c3ec-245d-4a60-865c-b8946d788eb9" width="45%"/> <img src="https://github.com/PKU-YuanGroup/Open-Sora-Plan/assets/88202804/46ef714e-3e5b-492c-aec4-3793cb2260b5" width="45%"/>

## Video Reconstruction

Raw video here: [1](https://streamable.com/gqojal), [2](https://streamable.com/6nu3j8).

https://github.com/PKU-YuanGroup/Open-Sora-Plan/assets/88202804/c100bb02-2420-48a3-9d7b-4608a41f14aa

https://github.com/PKU-YuanGroup/Open-Sora-Plan/assets/88202804/8aa8f587-d9f1-4e8b-8a82-d3bf9ba91d68

## Model Structure

![image](https://github.com/PKU-YuanGroup/Open-Sora-Plan/assets/88202804/dea3053a-504a-4a8d-ad5f-ace837891363)


The Causal Video VAE architecture inherits from the [Stable-Diffusion Image VAE](https://github.com/CompVis/stable-diffusion/tree/main). To ensure that the pretrained weights of the Image VAE can be seamlessly applied to the Video VAE, the model structure has been designed as follows:

1. Lossless Spatial Inheritance: By substituting 2D convolutions with causal 3D convolutions and employing a specific initialization method (tail init), the model ensures that when processing videos, the output for each frame is independent and consistent with the results of processing images individually, preserving the lossless transmission of spatial information.
2. Lossless Temporal Compression: After spatial processing, temporal compression is achieved through average pooling, which does not alter spatial information. By merging the time and batch dimensions in the attention mechanism, the impact of temporal variations on spatial information is minimized. Additionally, temporal difference upsampling is used to ensure the quality of spatial information remains unimpaired. These designs guarantee that the Video VAE maintains the high quality of the Image VAE in the spatial domain while focusing the training on optimizing temporal continuity.

## Training Details

<img width="833" alt="image" src="https://github.com/PKU-YuanGroup/Open-Sora-Plan/assets/88202804/9ffb6dc4-23f6-4274-a066-bbebc7522a14">

Here, we present our experiments on the initialization of convolutional kernel weights. The yellow curve represents the results using tail init, while the blue curve corresponds to the results from center init. As shown in the graph, tail init demonstrates better performance on the loss curve. Additionally, experiments found that center init leads to error accumulation, causing the collapse of video images over extended durations.