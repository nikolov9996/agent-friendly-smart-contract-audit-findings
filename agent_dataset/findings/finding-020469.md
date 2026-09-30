---
id: 20469
severity: "High"
---

# recipientsCounter should start from 1 in

## Description

DonationVotingMerkleDistributionBaseStrategy._registerRecipient calls _getUintRecipientStatus to get the current status of the application. The status of the new application should be Status.None. Then, the recipientToStatusIndexes[recipientId] to recipientsCounter and allo-v2/contracts/strategies/donation-voting-merkle-base/DonationVotingMerkleDistributionBaseStrategy.sol#L580

```solidity
function _registerRecipient(bytes memory _data, address _sender)
    internal
    override
    onlyActiveRegistration
    returns (address recipientId)
{
    uint8 currentStatus = _getUintRecipientStatus(recipientId);
    if (currentStatus == uint8(Status.None)) {
        // recipient registering new application
        recipientToStatusIndexes[recipientId] = recipientsCounter;
        _setRecipientStatus(recipientId, uint8(Status.Pending));
        bytes memory extendedData = abi.encode(_data, recipientsCounter);
        emit Registered(recipientId, extendedData, _sender);
        recipientsCounter++;
    } else {
        if (currentStatus == uint8(Status.Accepted)) {
            // recipient updating accepted application
            _setRecipientStatus(recipientId, uint8(Status.Pending));
        } else if (currentStatus == uint8(Status.Rejected)) {
            // recipient updating rejected application
            _setRecipientStatus(recipientId, uint8(Status.Appealed));
        }
        emit UpdatedRegistration(recipientId, _data, _sender, _getUintRecipientStatus(recipientId));
    }
}
```

DonationVotingMerkleDistributionBaseStrategy._getUintRecipientStatus calls _getStatusRowColumn to get the column index and current row. https://github.com/sting-merkle-base/DonationVotingMerkleDistributionBaseStrategy.sol#L819

```solidity
function _getUintRecipientStatus(address _recipientId) internal view returns (uint8 status) {
    // Get the column index and current row
    (, uint256 colIndex, uint256 currentRow) = _getStatusRowColumn(_recipientId);
    // Get the status from the 'currentRow' shifting by the 'colIndex'
    status = uint8((currentRow >> colIndex) & 15);
    // Return the status
    return status;
}
```

DonationVotingMerkleDistributionBaseStrategy._getStatusRowColumn computes indexes from recipientToStatusIndexes[_recipientId]. For the new recipient. blob/main/allo-v2/contracts/strategies/donation-voting-merkle-base/DonationVotingMerkleDistributionBaseStrategy.sol#L833

```solidity
function _getStatusRowColumn(address _recipientId) internal view returns (uint256, uint256, uint256) {
    uint256 recipientIndex = recipientToStatusIndexes[_recipientId];
    uint256 rowIndex = recipientIndex / 64; // 256 / 4
    uint256 colIndex = (recipientIndex % 64) * 4;
    return (rowIndex, colIndex, statusesBitMap[rowIndex]);
}
```

erkle-base/DonationVotingMerkleDistributionBaseStrategy.sol#L166

```solidity
/// @notice The total number of recipients.
uint256 public recipientsCounter;
```

Consider the following situation:
• Alice is the first recipient calls registerRecipient
// in _registerRecipient
recipientToStatusIndexes[Alice] = recipientsCounter = 0;
_setRecipientStatus(Alice, uint8(Status.Pending));
recipientCounter++
• Bob calls registerRecipient.
// in _getStatusRowColumn
recipientToStatusIndexes[Bob] = 0 // It would access the status of Alice
// in _registerRecipient
currentStatus = _getUintRecipientStatus(recipientId) = Status.Pending
currentStatus != uint8(Status.None) -> no new application is recorded in the pool.

This implementation error makes the pool can only record the first application.

## Proof of Concept

no poc

## Recommendation

Make the counter start from 1. There are two methods to fix the issue.
1.
```solidity
/// @notice The total number of recipients.
uint256 public recipientsCounter;
```
2.
```solidity
function _registerRecipient(bytes memory _data, address _sender)
    internal
    override
    onlyActiveRegistration
    returns (address recipientId)
{
    ...
    uint8 currentStatus = _getUintRecipientStatus(recipientId);
    if (currentStatus == uint8(Status.None)) {
        // recipient registering new application
        recipientToStatusIndexes[recipientId] = recipientsCounter + 1;
        _setRecipientStatus(recipientId, uint8(Status.Pending));
        bytes memory extendedData = abi.encode(_data, recipientsCounter);
        emit Registered(recipientId, extendedData, _sender);
        recipientsCounter++;
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an off‑by‑one indexing error in the recipient registration logic of the DonationVotingMerkleDistributionBaseStrategy contract. The contract keeps a public counter called recipientsCounter that starts at the default value 0. When a new recipient calls _registerRecipient, the function first reads the current status of the address by calling _getUintRecipientStatus, which in turn reads a bitmap based on an index stored in the mapping recipientToStatusIndexes. Because the mapping returns 0 for any address that has not been registered, the status lookup for a brand‑new recipient uses the same index (0) that belongs to the first registered recipient. Consequently, the status returned is not Status.None but the actual status of the first recipient (typically Pending). The registration code then treats the address as an existing application and does not create a new entry, so only the first applicant can ever be recorded in the pool. This flaw occurs every time a second or later recipient attempts to register, under the condition that the contract’s recipientsCounter has not been offset before the status check. The affected parties are the recipients who try to join the distribution, the donors whose funds are meant to be allocated to them, and the protocol itself because the distribution list becomes incomplete, breaking the intended accounting and potentially leaving funds undistributed. The issue was discovered during a manual audit that examined the flow of _registerRecipient and noticed that the status lookup happens before the mapping entry is written, and that the default zero value of the mapping collides with the legitimate index of the first recipient. It is hard to notice because the contract does not revert; it simply emits an UpdatedRegistration event with an unexpected status, making the failure appear as a silent update rather than a registration error. The bug belongs to the class of “default‑value collision” or “zero‑index reuse” bugs, where a data structure that relies on a zero‑initialized mapping cannot distinguish between an uninitialized entry and a legitimate entry that uses index zero. From a user’s perspective, a recipient after the first sees no registration event, their UI shows that they are not listed, or they receive a message that their application was not accepted even though they submitted it correctly. The business logic that assumes each new applicant receives a unique, sequential identifier is violated, leading to missing or undistributed funds. The recommended fix is to avoid using zero as a valid index: either initialise recipientsCounter to 1, store recipientsCounter+1 in the mapping, or add an explicit existence check before reading the status bitmap. By ensuring that the default mapping value (0) always represents “not yet registered”, the contract can correctly accept multiple recipients and preserve the intended distribution semantics.
