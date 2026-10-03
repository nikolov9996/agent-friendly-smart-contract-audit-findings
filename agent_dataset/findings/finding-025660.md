---
id: 25660
severity: "Crit/High"
---

# A user with a TapiocaOFT allowance >0 could steal all the underlying ERC20 tokens of the owner

## Description



## Proof of Concept

When a user wants to wrap a non-native ERC20 token into a TapiocaOFT they call `wrap` which calls `_wrap` under the hood:

function _wrap( address _fromAddress, address _toAddress, uint256 _amount ) internal virtual { if (_fromAddress != msg.sender) { require( allowance(_fromAddress, msg.sender) >= _amount, "TOFT_allowed" ); } IERC20(erc20).safeTransferFrom(_fromAddress, address(this), _amount); _mint(_toAddress, _amount); }

If the sender isn't the owner of the ERC20 tokens being wrapped, the allowance of the user is checked. However this isn't checking the underlying ERC20 allowance, but the allowance of the current contract (the TapiocaOFT).

Next, the underlying ERC20 token is transferred from the owner to this address. This decrements the allowance of the sender, however the sender isn't the original message sender, but this contract.

In order to use this contract as an owner (Alice) I would have to approve the `TapiocaOFT` contract to spend my ERC20 tokens, and it is common to approve this contract to spend all my tokens if I trust the contract. Now let's say I approved another user (Bob) to spend some (let's say 5) of my `TapiocaOFT` tokens. Bob can now call `wrap(aliceAddress, bobAddress, 5)` as many times as he wants to steal all of Alice's tokens.

## Recommendation

In my opinion you shouldn't be able to wrap another user's ERC20 tokens into a different token, because this is a different action to spending. Also, there is no way to decrement the allowance of the user (of the TapiocaOFT token) in the same call as we aren't actually transferring any tokens; there is no function selector in the ERC20 spec to decrease an allowance from another contract.

Therefore I would suggest the following change:

diff --git a/contracts/tOFT/BaseTOFT.sol b/contracts/tOFT/BaseTOFT.sol index 5658a0a..e8b7f63 100644 --- a/contracts/tOFT/BaseTOFT.sol +++ b/contracts/tOFT/BaseTOFT.sol @@ -350,12 +350,7 @@ contract BaseTOFT is BaseTOFTStorage, ERC20Permit { address _toAddress, uint256 _amount ) internal virtual {

- if (_fromAddress != msg.sender) {
- require(
- allowance(_fromAddress, msg.sender) >= _amount,
- "TOFT_allowed"
- );
- }
- require (_fromAddress == msg.sender, "TOFT_allowed"); IERC20(erc20).safeTransferFrom(_fromAddress, address(this), _amount); _mint(_toAddress, _amount); }
