import json
import os
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer

# Set paths
model_name = "meta-llama/Llama-3.2-3B-Instruct"
dataset_path = "./datasets/detector1.json" 
output_dir = "./fine_tuned_model"

def main():
    print("Loading dataset...")
    # Load dataset
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    formatted_data = []
    for item in data:
        instruction = item.get('instruction', '')
        input_text = item.get('input', '')
        output = item.get('output', '')
        
        formatted_data.append({
            "conversations": [
                {"role": "user", "content": f"{instruction}\n\n{input_text}"},
                {"role": "assistant", "content": output}
            ]
        })
    
    dataset = Dataset.from_list(formatted_data)
    print(f"Dataset loaded with {len(dataset)} examples")
    
    print("Loading model...")
    # Configure quantization
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )
    
    # Load model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto"
    )
    
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    print("Setting up LoRA...")
    # Set up LoRA
    lora_config = LoraConfig(
        r=16,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", 
                       "gate_proj", "up_proj", "down_proj"]
    )
    
    model = get_peft_model(model, lora_config)
    
    # Format dataset for training
    def formatting_prompts_func(examples):
        convos = examples["conversations"]
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) 
                for convo in convos]
        return {"text": texts}
    
    print("Preparing dataset for training...")
    formatted_dataset = dataset.map(formatting_prompts_func, batched=True)
    
    # Set up training arguments
    training_args = TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=50,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=1,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        save_strategy="steps",
        save_steps=10,
        output_dir=output_dir,
        overwrite_output_dir=True,
        report_to="none"
    )
    
    print("Setting up trainer...")
    # Set up trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=formatted_dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        args=training_args,
    )
    
    print("Starting fine-tuning...")
    # Start fine-tuning
    trainer.train()
    
    print("Saving fine-tuned model...")
    # Save fine-tuned model
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print(f"Fine-tuning completed! Model saved to {output_dir}")

if __name__ == "__main__":
    main()
