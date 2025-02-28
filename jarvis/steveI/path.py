from pathlib import Path

VPT_MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "weights" / "vpt" / "2x.model"
VPT_WEIGHT_PATH = Path(__file__).parent.parent.parent / "data" / "weights" / "steve1" / "steve1.weights"
PRIOR_WEIGHT_PATH = Path(__file__).parent.parent.parent / "data" / "weights" / "steve1" / "steve1_prior.pt"
MINECLIP_WEIGHT_PATH = Path(__file__).parent.parent.parent / "data" / "weights" / "mineclip" / "attn.pth"