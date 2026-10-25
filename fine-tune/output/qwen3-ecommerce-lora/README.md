---
library_name: peft
license: other
base_model: /root/autodl-tmp/models/Qwen3-8B
tags:
- base_model:adapter:/root/autodl-tmp/models/Qwen3-8B
- llama-factory
- lora
- transformers
pipeline_tag: text-generation
model-index:
- name: qwen3-ecommerce-lora
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# qwen3-ecommerce-lora

This model is a fine-tuned version of [/root/autodl-tmp/models/Qwen3-8B](https://huggingface.co//root/autodl-tmp/models/Qwen3-8B) on the ecommerce_demo dataset.
It achieves the following results on the evaluation set:
- Loss: 4.1342

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 0.0001
- train_batch_size: 1
- eval_batch_size: 1
- seed: 42
- gradient_accumulation_steps: 4
- total_train_batch_size: 4
- optimizer: Use OptimizerNames.ADAMW_TORCH_FUSED with betas=(0.9,0.999) and epsilon=1e-08 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: cosine
- lr_scheduler_warmup_ratio: 0.1
- num_epochs: 3

### Training results



### Framework versions

- PEFT 0.18.1
- Transformers 4.57.1
- Pytorch 2.14.1+cu130
- Datasets 4.0.0
- Tokenizers 0.22.2