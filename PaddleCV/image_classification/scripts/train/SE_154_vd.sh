#Training details
#GPU: NVIDIA® Tesla® P40 8cards 200epochs 916h
export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
export FLAGS_fast_eager_deletion_mode=1
export FLAGS_eager_delete_tensor_gb=0.0
export FLAGS_fraction_of_gpu_memory_to_use=0.98

#SE_154
python train.py \
            --model=SE_154_vd \
            --batch_size=256 \
            --total_images=1281167 \
            --image_shape=3,224,224 \
            --class_dim=1000 \
            --lr_strategy=cosine_decay \
            --lr=0.1 \
            --num_epochs=200 \
            --model_save_dir=output/ \
            --l2_decay=1e-4 \
            --use_mixup=True \
            --use_label_smoothing=True \
            --label_smoothing_epsilon=0.1 \
