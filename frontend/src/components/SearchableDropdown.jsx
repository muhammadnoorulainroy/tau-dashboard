import React, { useState, useRef, useEffect } from 'react';
import { ChevronDownIcon, XMarkIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';

/**
 * A searchable dropdown component that allows filtering options by text
 * 
 * @param {Object} props
 * @param {Array} props.options - Array of option objects with { id, username, email } or custom fields
 * @param {string|number|null} props.value - Currently selected value (id)
 * @param {Function} props.onChange - Callback when selection changes (receives option id or null)
 * @param {string} props.placeholder - Placeholder text for the input
 * @param {Function} props.renderOption - Function to render each option (receives option object)
 * @param {Function} props.filterOption - Function to filter options (receives option and searchTerm)
 * @param {string} props.emptyText - Text to display when no options match
 * @param {string} props.className - Additional CSS classes for the container
 */
const SearchableDropdown = ({
  options = [],
  value = null,
  onChange,
  placeholder = 'Select an option',
  renderOption = (option) => option.label || option.username || option.name,
  filterOption = (option, searchTerm) => {
    const term = searchTerm.toLowerCase();
    const username = (option.username || '').toLowerCase();
    const email = (option.email || '').toLowerCase();
    const name = (option.name || '').toLowerCase();
    return username.includes(term) || email.includes(term) || name.includes(term);
  },
  emptyText = 'No options found',
  className = ''
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  // Find the currently selected option
  const selectedOption = value ? options.find(opt => opt.id === value) : null;

  // Filter options based on search term
  const filteredOptions = searchTerm
    ? options.filter(opt => filterOption(opt, searchTerm))
    : options;

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus input when dropdown opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleToggle = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      setSearchTerm('');
    }
  };

  const handleSelect = (option) => {
    onChange(option ? option.id : null);
    setIsOpen(false);
    setSearchTerm('');
  };

  const handleClear = (e) => {
    e.stopPropagation();
    onChange(null);
    setSearchTerm('');
  };

  return (
    <div ref={dropdownRef} className={`relative ${className}`}>
      {/* Dropdown trigger button */}
      <div
        onClick={handleToggle}
        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white cursor-pointer focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 flex items-center justify-between"
      >
        <div className="flex-1 truncate">
          {selectedOption ? (
            <span className="text-sm text-gray-900">
              {renderOption(selectedOption)}
            </span>
          ) : (
            <span className="text-sm text-gray-500">{placeholder}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {selectedOption && (
            <button
              onClick={handleClear}
              className="p-0.5 hover:bg-gray-200 rounded"
              type="button"
            >
              <XMarkIcon className="h-4 w-4 text-gray-500" />
            </button>
          )}
          <ChevronDownIcon
            className={`h-4 w-4 text-gray-500 transition-transform ${
              isOpen ? 'transform rotate-180' : ''
            }`}
          />
        </div>
      </div>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-80">
          {/* Search input */}
          <div className="p-2 border-b border-gray-200 sticky top-0 bg-white">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                ref={inputRef}
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search..."
                className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Options list */}
          <div className="max-h-64 overflow-y-auto">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => (
                <div
                  key={option.id}
                  onClick={() => handleSelect(option)}
                  className={`px-3 py-2 cursor-pointer hover:bg-blue-50 ${
                    selectedOption?.id === option.id ? 'bg-blue-100' : ''
                  }`}
                >
                  {renderOption(option)}
                </div>
              ))
            ) : (
              <div className="px-3 py-2 text-sm text-gray-500 text-center">
                {emptyText}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchableDropdown;

