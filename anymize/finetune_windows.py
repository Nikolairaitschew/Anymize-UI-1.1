import json
import os
import torch
import argparse
from tqdm import tqdm
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer

# Disable warnings
import warnings
warnings.filterwarnings("ignore")

def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune Llama 3.2 model on Windows")
    parser.add_argument("--model", type=str, default="meta-llama/Llama-3.2-3B-Instruct", 
                        help="Model name or path")
    parser.add_argument("--dataset", type=str, default="./datasets/detector1.json", 
                        help="Path to the dataset file")
    parser.add_argument("--output_dir", type=str, default="./fine_tuned_model", 
                        help="Directory to save the fine-tuned model")
    parser.add_argument("--max_steps", type=int, default=50, 
                        help="Number of training steps")
    parser.add_argument("--learning_rate", type=float, default=2e-4, 
                        help="Learning rate")
    parser.add_argument("--batch_size", type=int, default=2, 
                        help="Batch size per device")
    return parser.parse_args()

def load_dataset(dataset_path):
    print(f"\nLoading dataset from {dataset_path}...")
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    formatted_data = []
    for item in tqdm(data, desc="Formatting dataset"):
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
    return dataset

def load_model_and_tokenizer(model_name):
    print(f"\nLoading model and tokenizer from {model_name}...")
    print("This may take a few minutes...")
    
    # Configure quantization for memory efficiency
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
        device_map="auto",
        torch_dtype=torch.float16
    )
    
    # Configure tokenizer
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    
    print("Model and tokenizer loaded successfully!")
    return model, tokenizer

def setup_lora(model):
    print("\nSetting up LoRA for parameter-efficient fine-tuning...")
    lora_config = LoraConfig(
        r=16,                       # Rank of the update matrices
        lora_alpha=16,              # Alpha parameter for LoRA scaling
        lora_dropout=0.05,          # Dropout probability for LoRA layers
        bias="none",                # Whether to train bias parameters
        task_type="CAUSAL_LM",      # Task type
        target_modules=[            # Which modules to apply LoRA to
            "q_proj", "k_proj", "v_proj", "o_proj", 
            "gate_proj", "up_proj", "down_proj"
        ]
    )
    
    model = get_peft_model(model, lora_config)
    print(f"LoRA initialized with rank {lora_config.r} and alpha {lora_config.lora_alpha}")
    return model

def finetune_model(model, tokenizer, dataset, args):
    print("\nPreparing dataset for training...")
    
    # Format the dataset for training
    def formatting_prompts_func(examples):
        convos = examples["conversations"]
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) 
                for convo in convos]
        return {"text": texts}
    
    formatted_dataset = dataset.map(formatting_prompts_func, batched=True)
    
    # Set up training arguments
    training_args = TrainingArguments(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        fp16=True,
        logging_steps=1,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        save_strategy="steps",
        save_steps=10,
        output_dir=args.output_dir,
        overwrite_output_dir=True,
        report_to="none"
    )
    
    print("\nSetting up trainer...")
    print(f"Training configuration:")
    print(f"  - Batch size: {args.batch_size}")
    print(f"  - Learning rate: {args.learning_rate}")
    print(f"  - Max steps: {args.max_steps}")
    print(f"  - Output directory: {args.output_dir}")
    
    # Set up trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=formatted_dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        args=training_args,
    )
    
    print("\nStarting fine-tuning...")
    try:
        # Start fine-tuning
        trainer.train()
        print("\nFine-tuning completed successfully!")
    except Exception as e:
        print(f"\nError during fine-tuning: {str(e)}")
        return False
    
    print("\nSaving fine-tuned model...")
    # Save fine-tuned model
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    
    print(f"Model and tokenizer saved to {args.output_dir}")
    return True

def test_model(model_path, test_prompt):
    print(f"\nLoading fine-tuned model from {model_path}...")
    # Load fine-tuned model
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        torch_dtype=torch.float16
    )
    
    print("Model loaded successfully!")
    print(f"\nGenerating response for: {test_prompt}")
    
    # Format input
    messages = [{"role": "user", "content": test_prompt}]
    inputs = tokenizer.apply_chat_template(
        messages, 
        tokenize=True, 
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)
    
    # Generate response
    outputs = model.generate(
        input_ids=inputs, 
        max_new_tokens=512,
        temperature=0.7,
        top_p=0.9
    )
    
    # Decode response
    response = tokenizer.batch_decode(outputs)[0]
    print(f"\nModel response:\n{response}")

def main():
    print("=========================")
    print("Llama 3.2 Fine-tuning Tool")
    print("=========================")
    print("Designed for Windows compatibility")
    
    # Parse arguments
    args = parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load dataset
    dataset = load_dataset(args.dataset)
    
    # Load model and tokenizer
    model, tokenizer = load_model_and_tokenizer(args.model)
    
    # Setup LoRA
    model = setup_lora(model)
    
    # Fine-tune model
    success = finetune_model(model, tokenizer, dataset, args)
    
    if success:
        # Test the model with a sample prompt
        test_prompt = "Can you detect if this text contains any sensitive information: My name is John Doe and my credit card number is 4111-1111-1111-1111"
        test_model(args.output_dir, test_prompt)
    
    print("\nProcess completed!")

if __name__ == "__main__":
    main()
