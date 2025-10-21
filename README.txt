Notes to Self

1. To enter Virtual Envrionment:
    Set-ExecutionPolicy Unrestricted -Scope Process
    venv\Scripts\Activate.ps1

2. venv\Lib\site-packages\craft_text_detector\models\basenet\vgg16_bn.py
REPLACE:
    # from torchvision.models.vgg import model_urls
    from torchvision.models.vgg import VGG16_BN_Weights                              # replaced

    # model_urls["vgg16_bn"] = model_urls["vgg16_bn"].replace("https://", "http://")
    # vgg_pretrained_features = models.vgg16_bn(pretrained=pretrained).features
    weights = VGG16_BN_Weights.DEFAULT if pretrained else None                       # replaced
    vgg_pretrained_features = models.vgg16_bn(weights=weights).features              # replaced


