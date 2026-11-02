from dataset import SketchDataset
from torch.utils.data import DataLoader

dataset = SketchDataset()
loader = DataLoader(dataset, batch_size=4, shuffle=True)

images, masks = next(iter(loader))

print("Total samples:", len(dataset))
print("Image batch:", images.shape)
print("Mask batch:", masks.shape)
print("Mask classes:", masks.unique().tolist())