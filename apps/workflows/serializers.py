from rest_framework import serializers

from .services import TRANSITIONS


class TransitionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=sorted(TRANSITIONS))
