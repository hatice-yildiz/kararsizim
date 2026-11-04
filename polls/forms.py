from django import forms

from .models import MAX_OPTIONS, MIN_OPTIONS


class PollForm(forms.Form):
    question = forms.CharField(
        label="Soru",
        max_length=200,
        error_messages={
            "required": "Soru zorunludur.",
            "max_length": "Soru en fazla 200 karakter olabilir.",
        },
    )
    description = forms.CharField(
        label="Açıklama (opsiyonel)",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={"max_length": "Açıklama en fazla 500 karakter olabilir."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(1, MAX_OPTIONS + 1):
            self.fields[f"option_{i}"] = forms.CharField(
                label=f"Seçenek {i}",
                max_length=100,
                required=False,
                error_messages={"max_length": "Seçenek en fazla 100 karakter olabilir."},
            )

    @property
    def option_fields(self):
        return [self[f"option_{i}"] for i in range(1, MAX_OPTIONS + 1)]

    def clean(self):
        cleaned = super().clean()
        options = []
        seen = {}
        for i in range(1, MAX_OPTIONS + 1):
            name = f"option_{i}"
            text = (cleaned.get(name) or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                self.add_error(name, "Bu seçenek zaten eklenmiş.")
                continue
            seen[key] = name
            options.append(text)
        if len(options) < MIN_OPTIONS and not any(
            self.errors.get(f"option_{i}") for i in range(1, MAX_OPTIONS + 1)
        ):
            self.add_error("option_1", f"En az {MIN_OPTIONS} seçenek girmelisin.")
        cleaned["options"] = options
        return cleaned
