import os
# Set environment variable to disable torch.compile which is causing issues on Windows
os.environ["UNSLOTH_DISABLE_COMPILE"] = "1"

# Import Unsloth first as recommended in the warning
try:
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template
    from unsloth import is_bfloat16_supported
except ImportError:
    print("Installing Unsloth...")
    import subprocess
    subprocess.run(["pip", "install", "unsloth[cu118]"], check=True)
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template
    from unsloth import is_bfloat16_supported

import json
import torch
import gradio as gr
from datasets import Dataset
from tqdm.auto import tqdm
from transformers import TrainingArguments, DataCollatorForSeq2Seq
from trl import SFTTrainer

# Function to convert JSON file to dataset format
def json_to_dataset(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract instruction, input and output from the JSON
    formatted_data = []
    for item in data:
        instruction = item.get('instruction', '')
        input_text = item.get('input', '')
        output = item.get('output', '')
        
        # Format as conversation for finetuning
        formatted_data.append({
            "conversations": [
                {"role": "user", "content": f"{instruction}\n\n{input_text}"},
                {"role": "assistant", "content": output}
            ]
        })
    
    return Dataset.from_list(formatted_data)

# Function to load and prepare model for fine-tuning
def load_model(model_name, max_seq_length=2048):
    # Load model with optimizations
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        dtype=None,  # Auto detect dtype
        load_in_4bit=True  # Use 4-bit quantization
    )
    
    # Set up LoRA for efficient fine-tuning
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,  # LoRA rank
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", 
                       "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
        use_rslora=False,
    )
    
    return model, tokenizer

# Fine-tuning function
def finetune_model(model, tokenizer, dataset, output_dir, progress=None):
    # Format the dataset for training
    def formatting_prompts_func(examples):
        convos = examples["conversations"]
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) 
                for convo in convos]
        return {"text": texts}
    
    formatted_dataset = dataset.map(formatting_prompts_func, batched=True)
    
    # Set up trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=formatted_dataset,
        dataset_text_field="text",
        max_seq_length=model.config.max_position_embeddings,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer),
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            max_steps=100,  # Adjust based on dataset size
            learning_rate=2e-4,
            fp16=not is_bfloat16_supported(),
            bf16=is_bfloat16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=output_dir,
        ),
    )
    
    # Custom callback to update progress bar
    class ProgressCallback:
        def __init__(self, progress_bar):
            self.progress_bar = progress_bar
            
        def on_step_end(self, args, state, control, **kwargs):
            if self.progress_bar is not None:
                self.progress_bar(state.global_step / state.max_steps)
    
    # Add progress callback if provided
    if progress is not None:
        trainer.add_callback(ProgressCallback(progress))
    
    # Train the model
    trainer.train()
    
    # Save the fine-tuned model
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    return model, tokenizer

# Function to generate text using the fine-tuned model
def generate_text(model, tokenizer, prompt, max_new_tokens=512):
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages, 
        tokenize=True, 
        add_generation_prompt=True,
        return_tensors="pt"
    ).to(model.device)
    
    # Generate response
    outputs = model.generate(
        input_ids=inputs, 
        max_new_tokens=max_new_tokens,
        use_cache=True,
        temperature=0.7,
        top_p=0.9
    )
    
    # Decode and return the response
    response = tokenizer.batch_decode(outputs)[0]
    # Extract only the assistant's response
    try:
        response = response.split("<|start_header_id|>assistant<|end_header_id|>\n\n")[1]
    except IndexError:
        pass  # In case the expected format isn't found
    
    return response

# Gradio UI
def create_ui():
    with gr.Blocks(title="Llama 3.2-3B Fine-tuning App") as app:
        gr.Markdown("# 🦙 Llama 3.2-3B Fine-tuning App")
        gr.Markdown("Upload a dataset in the format of detector1.json to fine-tune the Llama 3.2-3B model.")
        
        with gr.Tab("Fine-tune Model"):
            # Model selection
            model_name = gr.Dropdown(
                ["unsloth/Llama-3.2-3B-Instruct", "meta-llama/Llama-3.2-3B-Instruct"],
                label="Model",
                value="unsloth/Llama-3.2-3B-Instruct",
                info="Select the model to fine-tune"
            )
            
            # Dataset upload
            dataset_file = gr.File(
                label="Upload Dataset (JSON format)",
                file_types=["json"],
                info="Upload a dataset file in the same format as detector1.json"
            )
            
            # Preview dataset button and output
            preview_btn = gr.Button("Preview Dataset")
            preview_output = gr.JSON(label="Dataset Preview")
            
            # Training parameters
            with gr.Row():
                epochs = gr.Slider(
                    minimum=1, maximum=10, value=1, step=1,
                    label="Number of Epochs"
                )
                learning_rate = gr.Dropdown(
                    ["2e-4", "1e-4", "5e-5", "2e-5"],
                    label="Learning Rate",
                    value="2e-4"
                )
                max_seq_length = gr.Slider(
                    minimum=512, maximum=4096, value=2048, step=512,
                    label="Max Sequence Length"
                )
            
            # Output directory
            output_dir = gr.Textbox(
                label="Output Directory",
                value="./fine_tuned_model",
                info="Directory to save the fine-tuned model"
            )
            
            # Training progress
            train_btn = gr.Button("Start Fine-tuning")
            progress = gr.Progress(label="Fine-tuning Progress")
            status_output = gr.Textbox(label="Status")
            
        with gr.Tab("Test Fine-tuned Model"):
            # Load model selection
            model_path = gr.Textbox(
                label="Model Path",
                value="./fine_tuned_model",
                info="Path to the fine-tuned model"
            )
            load_model_btn = gr.Button("Load Model")
            load_status = gr.Textbox(label="Load Status")
            
            # Test input and output
            test_input = gr.Textbox(
                label="Input Text",
                placeholder="Enter test prompt here...",
                lines=5
            )
            generate_btn = gr.Button("Generate Response")
            test_output = gr.Textbox(label="Generated Response", lines=10)
        
        # Define event handlers
        def preview_dataset(file):
            if file is None:
                return {"error": "No file uploaded"}
            try:
                with open(file.name, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Return first 2 items for preview
                return data[:2] if len(data) > 2 else data
            except Exception as e:
                return {"error": str(e)}
        
        preview_btn.click(preview_dataset, inputs=[dataset_file], outputs=[preview_output])
        
        # Variables to store model and tokenizer
        fine_tuned_model = None
        fine_tuned_tokenizer = None
        
        def finetune(model_name, file, epochs, lr, seq_len, out_dir, progress=gr.Progress()):
            if file is None:
                return "Error: No dataset file uploaded."
            
            try:
                # Convert string learning rate to float
                lr_float = float(lr)
                
                # Create output directory if it doesn't exist
                os.makedirs(out_dir, exist_ok=True)
                
                # Load and prepare dataset
                progress(0.1, desc="Loading dataset...")
                dataset = json_to_dataset(file.name)
                
                # Load model
                progress(0.2, desc="Loading model...")
                model, tokenizer = load_model(model_name, max_seq_length=seq_len)
                
                # Fine-tune model
                progress(0.3, desc="Fine-tuning started...")
                finetune_model(model, tokenizer, dataset, out_dir, 
                              progress=lambda p: progress(0.3 + 0.6 * p, desc=f"Training: {int(p*100)}%"))
                
                progress(1.0, desc="Fine-tuning completed!")
                return f"Fine-tuning completed! Model saved to {out_dir}"
            except Exception as e:
                return f"Error during fine-tuning: {str(e)}"
        
        train_btn.click(
            finetune,
            inputs=[model_name, dataset_file, epochs, learning_rate, max_seq_length, output_dir],
            outputs=[status_output]
        )
        
        def load_fine_tuned_model(model_path):
            nonlocal fine_tuned_model, fine_tuned_tokenizer
            try:
                # Load the fine-tuned model
                fine_tuned_model, fine_tuned_tokenizer = FastLanguageModel.from_pretrained(
                    model_name=model_path,
                    max_seq_length=2048,  # This can be adjusted based on needs
                    dtype=None,  # Auto detect dtype
                    load_in_4bit=True  # Use 4-bit quantization for inference
                )
                
                # Set up for inference
                fine_tuned_model = FastLanguageModel.for_inference(fine_tuned_model)
                
                return f"Model loaded successfully from {model_path}"
            except Exception as e:
                return f"Error loading model: {str(e)}"
        
        load_model_btn.click(load_fine_tuned_model, inputs=[model_path], outputs=[load_status])
        
        def test_generate(prompt):
            if fine_tuned_model is None or fine_tuned_tokenizer is None:
                return "Error: No model loaded. Please load a model first."
            
            try:
                response = generate_text(fine_tuned_model, fine_tuned_tokenizer, prompt)
                return response
            except Exception as e:
                return f"Error generating response: {str(e)}"
        
        generate_btn.click(test_generate, inputs=[test_input], outputs=[test_output])
    
    return app

# Main function
def main():
    app = create_ui()
    app.launch(share=False, debug=True)

if __name__ == "__main__":
    main()
