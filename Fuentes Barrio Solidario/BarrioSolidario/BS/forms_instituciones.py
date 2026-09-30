from django import forms

from .models import InstitucionAval


class InstitucionAvalForm(forms.ModelForm):
    class Meta:
        model = InstitucionAval
        fields = ("nombre", "descripcion", "url", "imagen", "orden", "activa")
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "maxlength": 120}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 3, "maxlength": 240}),
            "url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://institucion.example", "maxlength": 300}),
            "imagen": forms.FileInput(attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}),
            "orden": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 999}),
            "activa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_imagen(self):
        archivo = self.cleaned_data.get("imagen")
        if archivo and archivo.size > 8 * 1024 * 1024:
            raise forms.ValidationError("La imagen debe pesar hasta 8 MB.")
        if archivo:
            from PIL import Image, UnidentifiedImageError
            try:
                archivo.seek(0)
                with Image.open(archivo) as imagen:
                    if imagen.format not in ("JPEG", "PNG", "WEBP"):
                        raise forms.ValidationError("Usa una imagen JPG, PNG o WebP.")
                    if imagen.width * imagen.height > 24_000_000:
                        raise forms.ValidationError("La imagen supera los 24 megapíxeles permitidos.")
                    imagen.verify()
            except (OSError, ValueError, UnidentifiedImageError):
                raise forms.ValidationError("No se pudo leer la imagen.")
            finally:
                archivo.seek(0)
        return archivo

    def clean_orden(self):
        valor = self.cleaned_data["orden"]
        if valor > 999:
            raise forms.ValidationError("El orden máximo es 999.")
        return valor

    def clean_url(self):
        valor = self.cleaned_data["url"].strip()
        if not valor.lower().startswith(("https://", "http://")):
            raise forms.ValidationError("Usa una dirección http o https del sitio oficial.")
        return valor
