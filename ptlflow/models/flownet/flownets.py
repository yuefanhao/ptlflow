"""
Portions of this code copyright 2017, Clement Pinard
"""

from einops import rearrange
import torch
import torch.nn as nn
from torch.nn import init

from ptlflow.utils.registry import register_model, trainable
from .submodules import *
from .flownet_base import FlowNetBase


class FlowNetS(FlowNetBase):
    pretrained_checkpoints = {
        "things": "https://github.com/hmorimitsu/ptlflow/releases/download/weights1/flownets-things-98cde14d.ckpt"
    }

    def __init__(
        self,
        div_flow: float = 20.0,
        input_channels: int = 6,
        batch_norm: bool = False,
        loss_start_scale: int = 4,
        loss_num_scales: int = 5,
        loss_base_weight: float = 0.32,
        loss_norm: str = "L2",
        **kwargs,
    ):
        super(FlowNetS, self).__init__(
            div_flow=div_flow,
            input_channels=input_channels,
            batch_norm=batch_norm,
            loss_start_scale=loss_start_scale,
            loss_num_scales=loss_num_scales,
            loss_base_weight=loss_base_weight,
            loss_norm=loss_norm,
            **kwargs,
        )

        self.conv1 = conv(
            self.batch_norm, self.input_channels, 64, kernel_size=7, stride=2
        )
        self.conv2 = conv(self.batch_norm, 64, 128, kernel_size=5, stride=2)
        self.conv3 = conv(self.batch_norm, 128, 256, kernel_size=5, stride=2)
        self.conv3_1 = conv(self.batch_norm, 256, 256)
        self.conv4 = conv(self.batch_norm, 256, 512, stride=2)
        self.conv4_1 = conv(self.batch_norm, 512, 512)
        self.conv5 = conv(self.batch_norm, 512, 512, stride=2)
        self.conv5_1 = conv(self.batch_norm, 512, 512)
        self.conv6 = conv(self.batch_norm, 512, 1024, stride=2)
        self.conv6_1 = conv(self.batch_norm, 1024, 1024)

        self.deconv5 = deconv(1024, 512)
        self.deconv4 = deconv(1026, 256)
        self.deconv3 = deconv(770, 128)
        self.deconv2 = deconv(386, 64)

        self.predict_flow6 = predict_flow(1024)
        self.predict_flow5 = predict_flow(1026)
        self.predict_flow4 = predict_flow(770)
        self.predict_flow3 = predict_flow(386)
        self.predict_flow2 = predict_flow(194)

        self.upsampled_flow6_to_5 = nn.ConvTranspose2d(2, 2, 4, 2, 1, bias=False)
        self.upsampled_flow5_to_4 = nn.ConvTranspose2d(2, 2, 4, 2, 1, bias=False)
        self.upsampled_flow4_to_3 = nn.ConvTranspose2d(2, 2, 4, 2, 1, bias=False)
        self.upsampled_flow3_to_2 = nn.ConvTranspose2d(2, 2, 4, 2, 1, bias=False)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                if m.bias is not None:
                    init.uniform_(m.bias)
                init.xavier_uniform_(m.weight)

            if isinstance(m, nn.ConvTranspose2d):
                if m.bias is not None:
                    init.uniform_(m.bias)
                init.xavier_uniform_(m.weight)
                # init_deconv_bilinear(m.weight)
        self.upsample1 = nn.Upsample(
            scale_factor=4, mode="bilinear", align_corners=False
        )

    def forward(self, inputs, skip_preprocess=False):
        images = inputs["images"]
        if skip_preprocess:
            image_resizer = None
        else:
            bgr_mean = rearrange(images, "b n c h w -> b n c (h w)").mean(-1)
            bgr_mean = bgr_mean[..., None, None]
            images, image_resizer = self.preprocess_images(
                images,
                bgr_add=-bgr_mean,
                bgr_mult=1.0,
                bgr_to_rgb=True,
                resize_mode="interpolation",
                interpolation_mode="bilinear",
                interpolation_align_corners=True,
            )
        x = images

        x = x.view(x.shape[0], x.shape[1] * x.shape[2], x.shape[3], x.shape[4])
        out_conv1 = self.conv1(x)

        out_conv2 = self.conv2(out_conv1)
        out_conv3 = self.conv3_1(self.conv3(out_conv2))
        out_conv4 = self.conv4_1(self.conv4(out_conv3))
        out_conv5 = self.conv5_1(self.conv5(out_conv4))
        out_conv6 = self.conv6_1(self.conv6(out_conv5))

        flow6 = self.predict_flow6(out_conv6)
        flow6_up = self.upsampled_flow6_to_5(flow6)
        out_deconv5 = self.deconv5(out_conv6)

        concat5 = torch.cat((out_conv5, out_deconv5, flow6_up), 1)
        flow5 = self.predict_flow5(concat5)
        flow5_up = self.upsampled_flow5_to_4(flow5)
        out_deconv4 = self.deconv4(concat5)

        concat4 = torch.cat((out_conv4, out_deconv4, flow5_up), 1)
        flow4 = self.predict_flow4(concat4)
        flow4_up = self.upsampled_flow4_to_3(flow4)
        out_deconv3 = self.deconv3(concat4)

        concat3 = torch.cat((out_conv3, out_deconv3, flow4_up), 1)
        flow3 = self.predict_flow3(concat3)
        flow3_up = self.upsampled_flow3_to_2(flow3)
        out_deconv2 = self.deconv2(concat3)

        concat2 = torch.cat((out_conv2, out_deconv2, flow3_up), 1)
        flow2 = self.predict_flow2(concat2)

        out_flow = self.div_flow * self.upsample1(flow2)
        if image_resizer is not None:
            out_flow = self.postprocess_predictions(
                out_flow, image_resizer, is_flow=True
            )

        outputs = {}

        if self.training:
            outputs["flow_preds"] = [
                flow2,
                flow3,
                flow4,
                flow5,
                flow6,
            ]
            outputs["flows"] = out_flow[:, None]
        else:
            outputs["flows"] = out_flow[:, None]

        return outputs


@register_model
@trainable
class flownets(FlowNetS):
    pass
