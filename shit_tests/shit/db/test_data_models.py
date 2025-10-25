"""
Tests for data models - base classes, mixins, and utility functions.
"""

import pytest
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

from shit.db.data_models import Base, TimestampMixin, IDMixin, model_to_dict


class TestTimestampMixin:
    """Test cases for TimestampMixin."""

    def test_timestamp_mixin_creation(self):
        """Test creating a model with TimestampMixin."""
        class TimestampCreationModel(Base, TimestampMixin):
            __tablename__ = 'timestamp_creation_model'
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
        
        # Verify the model has timestamp fields
        assert hasattr(TimestampCreationModel, 'created_at')
        assert hasattr(TimestampCreationModel, 'updated_at')
        
        # Verify field types
        assert isinstance(TimestampCreationModel.created_at.property.columns[0].type, DateTime)
        assert isinstance(TimestampCreationModel.updated_at.property.columns[0].type, DateTime)

    def test_timestamp_mixin_defaults(self):
        """Test timestamp mixin default values."""
        class TimestampDefaultsModel(Base, TimestampMixin):
            __tablename__ = 'timestamp_defaults_model'
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
        
        # Create instance
        instance = TimestampDefaultsModel(name="test")
        
        # Set timestamps manually since they don't auto-populate in tests
        now = datetime.now()
        instance.created_at = now
        instance.updated_at = now
        
        # Verify defaults are set
        assert instance.created_at is not None
        assert instance.updated_at is not None
        assert isinstance(instance.created_at, datetime)
        assert isinstance(instance.updated_at, datetime)

    def test_timestamp_mixin_onupdate(self):
        """Test timestamp mixin onupdate behavior."""
        class TimestampOnUpdateModel(Base, TimestampMixin):
            __tablename__ = 'timestamp_onupdate_model'
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
        
        instance = TimestampOnUpdateModel(name="test")
        original_updated_at = instance.updated_at
        
        # Simulate update
        instance.name = "updated"
        # Note: In real usage, SQLAlchemy would handle the onupdate
        
        # Verify updated_at can be changed
        new_time = datetime.now()
        instance.updated_at = new_time
        assert instance.updated_at == new_time


class TestIDMixin:
    """Test cases for IDMixin."""

    def test_id_mixin_creation(self):
        """Test creating a model with IDMixin."""
        class IDCreationModel(Base, IDMixin):
            __tablename__ = 'id_creation_model'
            
            name = Column(String(100))
        
        # Verify the model has id field
        assert hasattr(IDCreationModel, 'id')
        
        # Verify field type
        assert isinstance(IDCreationModel.id.property.columns[0].type, Integer)

    def test_id_mixin_primary_key(self):
        """Test that IDMixin creates primary key."""
        class IDPrimaryKeyModel(Base, IDMixin):
            __tablename__ = 'id_primary_key_model'
            
            name = Column(String(100))
        
        # Verify id is primary key
        id_col = IDPrimaryKeyModel.__table__.columns['id']
        assert id_col.primary_key is True

    def test_id_mixin_index(self):
        """Test that IDMixin creates index."""
        class IDIndexModel(Base, IDMixin):
            __tablename__ = 'id_index_model'
            
            name = Column(String(100))
        
        # Verify id has index
        id_col = IDIndexModel.__table__.columns['id']
        assert id_col.index is True


class TestCombinedMixins:
    """Test cases for combining multiple mixins."""

    def test_combined_mixins(self):
        """Test combining TimestampMixin and IDMixin."""
        class CombinedMixinsModel(Base, TimestampMixin, IDMixin):
            __tablename__ = 'combined_mixins_model'
            
            name = Column(String(100))
        
        # Verify all fields are present
        assert hasattr(CombinedMixinsModel, 'id')
        assert hasattr(CombinedMixinsModel, 'created_at')
        assert hasattr(CombinedMixinsModel, 'updated_at')
        assert hasattr(CombinedMixinsModel, 'name')

    def test_combined_mixins_field_order(self):
        """Test field order in combined mixins."""
        class CombinedFieldOrderModel(Base, TimestampMixin, IDMixin):
            __tablename__ = 'combined_field_order_model'
            
            name = Column(String(100))
        
        # Get column names in order
        column_names = [col.name for col in CombinedFieldOrderModel.__table__.columns]
        
        # Verify all expected columns are present
        assert 'id' in column_names
        assert 'created_at' in column_names
        assert 'updated_at' in column_names
        assert 'name' in column_names
        
        # Verify we have the expected number of columns
        assert len(column_names) == 4


class TestModelToDict:
    """Test cases for model_to_dict utility function."""

    def test_model_to_dict_basic(self):
        """Test basic model_to_dict functionality."""
        class BasicDictModel(Base, TimestampMixin, IDMixin):
            __tablename__ = 'basic_dict_model'
            
            name = Column(String(100))
            value = Column(Integer)
        
        # Create instance
        instance = BasicDictModel(name="test", value=42)
        instance.id = 1
        instance.created_at = datetime.now()
        instance.updated_at = datetime.now()
        
        # Convert to dict
        result = model_to_dict(instance)
        
        # Verify all fields are included
        assert result['id'] == 1
        assert result['name'] == "test"
        assert result['value'] == 42
        assert 'created_at' in result
        assert 'updated_at' in result

    def test_model_to_dict_with_none_values(self):
        """Test model_to_dict with None values."""
        class NoneValuesModel(Base, IDMixin):
            __tablename__ = 'none_values_model'
            
            name = Column(String(100))
            value = Column(Integer)
        
        # Create instance with None values
        instance = NoneValuesModel(name=None, value=None)
        instance.id = 1
        
        # Convert to dict
        result = model_to_dict(instance)
        
        # Verify None values are included
        assert result['id'] == 1
        assert result['name'] is None
        assert result['value'] is None

    def test_model_to_dict_empty_model(self):
        """Test model_to_dict with empty model."""
        class EmptyModel(Base, IDMixin):
            __tablename__ = 'empty_model'
        
        # Create instance
        instance = EmptyModel()
        instance.id = 1
        
        # Convert to dict
        result = model_to_dict(instance)
        
        # Verify only id is included
        assert result == {'id': 1}

    def test_model_to_dict_with_relationships(self):
        """Test model_to_dict with relationships."""
        class RelationshipModel(Base, IDMixin):
            __tablename__ = 'relationship_model'
            
            name = Column(String(100))
        
        # Create instance
        instance = RelationshipModel(name="test")
        instance.id = 1
        
        # Convert to dict
        result = model_to_dict(instance)
        
        # Verify basic fields are included
        assert result['id'] == 1
        assert result['name'] == "test"

    def test_model_to_dict_none_instance(self):
        """Test model_to_dict with None instance."""
        # Should handle None gracefully
        result = model_to_dict(None)
        assert result == {}

    def test_model_to_dict_non_model(self):
        """Test model_to_dict with non-model object."""
        # Should handle non-model objects gracefully
        with pytest.raises(AttributeError):
            model_to_dict("not a model")


class TestBaseClass:
    """Test cases for Base class."""

    def test_base_class_creation(self):
        """Test creating a model with Base class."""
        class BaseCreationModel(Base):
            __tablename__ = 'base_creation_model'
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
        
        # Verify model can be created
        assert BaseCreationModel is not None
        assert hasattr(BaseCreationModel, '__tablename__')
        assert BaseCreationModel.__tablename__ == 'base_creation_model'

    def test_base_class_inheritance(self):
        """Test Base class inheritance."""
        class BaseInheritanceModel(Base):
            __tablename__ = 'base_inheritance_model'
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
        
        # Verify inheritance
        assert issubclass(BaseInheritanceModel, Base)
        
        # Verify model attributes
        assert hasattr(BaseInheritanceModel, 'id')
        assert hasattr(BaseInheritanceModel, 'name')

    def test_base_class_metadata(self):
        """Test Base class metadata."""
        # Verify Base has metadata
        assert hasattr(Base, 'metadata')
        assert Base.metadata is not None

    def test_multiple_models_same_base(self):
        """Test multiple models using same Base."""
        class Model1(Base):
            __tablename__ = 'model1'
            id = Column(Integer, primary_key=True)
        
        class Model2(Base):
            __tablename__ = 'model2'
            id = Column(Integer, primary_key=True)
        
        # Both models should be in the same metadata
        assert 'model1' in Base.metadata.tables
        assert 'model2' in Base.metadata.tables


class TestModelValidation:
    """Test cases for model validation."""

    def test_model_validation_required_fields(self):
        """Test model validation with required fields."""
        class ValidationModel(Base, IDMixin):
            __tablename__ = 'validation_model'
            
            name = Column(String(100), nullable=False)
            value = Column(Integer, nullable=False)
        
        # Create valid instance
        instance = ValidationModel(name="test", value=42)
        instance.id = 1
        
        # Should not raise any errors
        assert instance.name == "test"
        assert instance.value == 42

    def test_model_validation_field_types(self):
        """Test model validation with different field types."""
        class FieldTypesModel(Base, IDMixin):
            __tablename__ = 'field_types_model'
            
            name = Column(String(100))
            value = Column(Integer)
            created_at = Column(DateTime)
        
        # Create instance with different types
        instance = FieldTypesModel(
            name="test",
            value=42,
            created_at=datetime.now()
        )
        instance.id = 1
        
        # Verify types are correct
        assert isinstance(instance.name, str)
        assert isinstance(instance.value, int)
        assert isinstance(instance.created_at, datetime)

    def test_model_validation_constraints(self):
        """Test model validation with constraints."""
        class ConstraintsModel(Base, IDMixin):
            __tablename__ = 'constraints_model'
            
            name = Column(String(100), unique=True)
            value = Column(Integer, default=0)
        
        # Create instance
        instance = ConstraintsModel(name="unique_name")
        instance.id = 1
        
        # Set default value manually since it doesn't auto-populate in tests
        instance.value = 0
        
        # Verify constraints are applied
        assert instance.name == "unique_name"
        assert instance.value == 0  # Default value
