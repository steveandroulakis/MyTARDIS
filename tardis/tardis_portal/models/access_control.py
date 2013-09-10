from django.conf import settings
from django.contrib.auth.models import User, Group
from django.db import models

class UserProfileManager():
    """
    Added by Sindhu Emilda for natural key implementation.
    The manager for the tardis_portal's UserProfile model.
    """
    def get_by_natural_key(self, username):
        return self.get(user=User.objects.get_by_natural_key(username),
        )
        
class UserProfile(models.Model):
    """
    UserProfile class is an extension to the Django standard user model.

    :attribute isDjangoAccount: is the user a local DB user
    :attribute user: a foreign key to the
       :class:`django.contrib.auth.models.User`
    """
    user = models.ForeignKey(User, unique=True)

    # This flag will tell us if the main User account was created using any
    # non localdb auth methods. For example, if a first time user authenticates
    # to the system using the VBL auth method, an account will be created for
    # him, say "vbl_user001" and the field isDjangoAccount will be set to
    # False.
    isDjangoAccount = models.BooleanField(
        null=False, blank=False, default=True)

    ''' Added by Sindhu Emilda for natural key implementation '''
    objects = UserProfileManager()
    
    def natural_key(self):
        return self.user.natural_key()
    
    natural_key.dependencies = ['auth.User']

    class Meta:
        app_label = 'tardis_portal'

    def getUserAuthentications(self):
        return self.userAuthentication_set.all()

    def isValidPublicContact(self):
        '''
        Checks if there's enough information on the user for it to be used as
        a public contact.

        Note: Last name can't be required, because people don't necessarilly
        have a last (or family) name.
        '''
        required_fields = ['email', 'first_name']
        return all(map(lambda f: bool(getattr(self.user,f)), required_fields))

    def __unicode__(self):
        return self.user.username

class GroupAdminManager():
    """
    Added by Sindhu Emilda for natural key implementation.
    The manager for the tardis_portal's GroupAdmin model.
    """
    def get_by_natural_key(self, username, groupname):
        return self.get(user=User.objects.get_by_natural_key(username),
                        group=Group.objects.get_by_natural_key(groupname),
        )

class GroupAdmin(models.Model):
    """GroupAdmin links the Django User and Group tables for group
    administrators

    :attribute user: a forign key to the
       :class:`django.contrib.auth.models.User`
    :attribute group: a forign key to the
       :class:`django.contrib.auth.models.Group`
    """

    user = models.ForeignKey(User)
    group = models.ForeignKey(Group)

    ''' Added by Sindhu Emilda for natural key implementation '''
    objects = GroupAdminManager()
    
    def natural_key(self):
        return (self.user.natural_key(),) + self.group.natural_key()
    
    natural_key.dependencies = ['auth.User', 'auth.Group']

    class Meta:
        app_label = 'tardis_portal'

    def __unicode__(self):
        return '%s: %s' % (self.user.username, self.group.name)

class UserAuthenticationManager():
    """
    Added by Sindhu Emilda for natural key implementation.
    The manager for the tardis_portal's UserAuthentication model.
    """
    def get_by_natural_key(self, username):
        return self.get(userProfile=UserProfile.objects.get_by_natural_key(username),
        )

# TODO: Generalise auth methods
class UserAuthentication(models.Model):
    CHOICES = ()
    userProfile = models.ForeignKey(UserProfile)
    username = models.CharField(max_length=50)
    authenticationMethod = models.CharField(max_length=30, choices=CHOICES)

    ''' Added by Sindhu Emilda for natural key implementation '''
    objects = UserAuthenticationManager()
    
    def natural_key(self):
        return self.userProfile.natural_key()
    
    natural_key.dependencies = ['tardis_portal.UserProfile']

    class Meta:
        app_label = 'tardis_portal'

    def __init__(self, *args, **kwargs):
        # instantiate comparisonChoices based on settings.AUTH PROVIDERS
        self.CHOICES = ()
        for authMethods in settings.AUTH_PROVIDERS:
            self.CHOICES += ((authMethods[0], authMethods[1]),)
        self._comparisonChoicesDict = dict(self.CHOICES)

        super(UserAuthentication, self).__init__(*args, **kwargs)

    def getAuthMethodDescription(self):
        return self._comparisonChoicesDict[self.authenticationMethod]

    def __unicode__(self):
        return self.username + ' - ' + self.getAuthMethodDescription()


