# -*- coding:utf-8 -*-


from django.db import models
from django.utils.encoding import force_str


class KeyMap(models.Model):
    key = models.CharField(max_length=40, unique=True)
    value = models.CharField(max_length=100)
    accessed_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return force_str("%s => %s" % (self.key, self.value))
