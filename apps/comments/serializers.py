from rest_framework import serializers

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.EmailField(source="author.email", read_only=True, allow_null=True)
    body = serializers.CharField(max_length=2000)

    class Meta:
        model = Comment
        fields = ("id", "author", "body", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
