#copyright (c) 2019 PaddlePaddle Authors. All Rights Reserve.
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import paddle.fluid as fluid
from paddle.fluid.initializer import MSRA
from paddle.fluid.param_attr import ParamAttr

__all__ = [
    'MobileNetV2', 'MobileNetV2_x0_25, '
    'MobileNetV2_x0_5', 'MobileNetV2_x1_0', 'MobileNetV2_x1_5',
    'MobileNetV2_x2_0', 'MobileNetV2_scale'
]


class MobileNetV2():
    def __init__(self, scale=1.0, change_depth=False):
        self.scale = scale
        self.change_depth = change_depth

    def net(self, input, class_dim=1000):
        scale = self.scale
        change_depth = self.change_depth
        #if change_depth is True, the new depth is 1.4 times as deep as before.
        bottleneck_params_list = [
            (1, 16, 1, 1),
            (6, 24, 2, 2),
            (6, 32, 3, 2),
            (6, 64, 4, 2),
            (6, 96, 3, 1),
            (6, 160, 3, 2),
            (6, 320, 1, 1),
        ] if change_depth == False else [
            (1, 16, 1, 1),
            (6, 24, 2, 2),
            (6, 32, 5, 2),
            (6, 64, 7, 2),
            (6, 96, 5, 1),
            (6, 160, 3, 2),
            (6, 320, 1, 1),
        ]

        #conv1 
        input = self.conv_bn_layer(
            input,
            num_filters=int(32 * scale),
            filter_size=3,
            stride=2,
            padding=1,
            if_act=True,
            name='conv1_1')

        # bottleneck sequences
        i = 1
        in_c = int(32 * scale)
        for layer_setting in bottleneck_params_list:
            t, c, n, s = layer_setting
            i += 1
            input = self.invresi_blocks(
                input=input,
                in_c=in_c,
                t=t,
                c=int(c * scale),
                n=n,
                s=s,
                name='conv' + str(i))
            in_c = int(c * scale)
        #last_conv
        input = self.conv_bn_layer(
            input=input,
            num_filters=int(1280 * scale) if scale > 1.0 else 1280,
            filter_size=1,
            stride=1,
            padding=0,
            if_act=True,
            name='conv9')

        input = fluid.layers.pool2d(
            input=input,
            pool_size=7,
            pool_stride=1,
            pool_type='avg',
            global_pooling=True)

        output = fluid.layers.fc(input=input,
                                 size=class_dim,
                                 param_attr=ParamAttr(name='fc10_weights'),
                                 bias_attr=ParamAttr(name='fc10_offset'))
        return output

    def conv_bn_layer(self,
                      input,
                      filter_size,
                      num_filters,
                      stride,
                      padding,
                      channels=None,
                      num_groups=1,
                      if_act=True,
                      name=None,
                      use_cudnn=True):
        conv = fluid.layers.conv2d(
            input=input,
            num_filters=num_filters,
            filter_size=filter_size,
            stride=stride,
            padding=padding,
            groups=num_groups,
            act=None,
            use_cudnn=use_cudnn,
            param_attr=ParamAttr(name=name + '_weights'),
            bias_attr=False)
        bn_name = name + '_bn'
        bn = fluid.layers.batch_norm(
            input=conv,
            param_attr=ParamAttr(name=bn_name + "_scale"),
            bias_attr=ParamAttr(name=bn_name + "_offset"),
            moving_mean_name=bn_name + '_mean',
            moving_variance_name=bn_name + '_variance')
        if if_act:
            return fluid.layers.relu6(bn)
        else:
            return bn

    def shortcut(self, input, data_residual):
        return fluid.layers.elementwise_add(input, data_residual)

    def inverted_residual_unit(self,
                               input,
                               num_in_filter,
                               num_filters,
                               ifshortcut,
                               stride,
                               filter_size,
                               padding,
                               expansion_factor,
                               name=None):
        num_expfilter = int(round(num_in_filter * expansion_factor))

        channel_expand = self.conv_bn_layer(
            input=input,
            num_filters=num_expfilter,
            filter_size=1,
            stride=1,
            padding=0,
            num_groups=1,
            if_act=True,
            name=name + '_expand')

        bottleneck_conv = self.conv_bn_layer(
            input=channel_expand,
            num_filters=num_expfilter,
            filter_size=filter_size,
            stride=stride,
            padding=padding,
            num_groups=num_expfilter,
            if_act=True,
            name=name + '_dwise',
            use_cudnn=False)

        linear_out = self.conv_bn_layer(
            input=bottleneck_conv,
            num_filters=num_filters,
            filter_size=1,
            stride=1,
            padding=0,
            num_groups=1,
            if_act=False,
            name=name + '_linear')
        if ifshortcut:
            out = self.shortcut(input=input, data_residual=linear_out)
            return out
        else:
            return linear_out

    def invresi_blocks(self, input, in_c, t, c, n, s, name=None):
        first_block = self.inverted_residual_unit(
            input=input,
            num_in_filter=in_c,
            num_filters=c,
            ifshortcut=False,
            stride=s,
            filter_size=3,
            padding=1,
            expansion_factor=t,
            name=name + '_1')

        last_residual_block = first_block
        last_c = c

        for i in range(1, n):
            last_residual_block = self.inverted_residual_unit(
                input=last_residual_block,
                num_in_filter=last_c,
                num_filters=c,
                ifshortcut=True,
                stride=1,
                filter_size=3,
                padding=1,
                expansion_factor=t,
                name=name + '_' + str(i + 1))
        return last_residual_block


def MobileNetV2_x0_25():
    model = MobileNetV2(scale=0.25)
    return model


def MobileNetV2_x0_5():
    model = MobileNetV2(scale=0.5)
    return model


def MobileNetV2_x1_0():
    model = MobileNetV2(scale=1.0)
    return model


def MobileNetV2_x1_5():
    model = MobileNetV2(scale=1.5)
    return model


def MobileNetV2_x2_0():
    model = MobileNetV2(scale=2.0)
    return model


def MobileNetV2_scale():
    model = MobileNetV2(scale=1.2, change_depth=True)
    return model
